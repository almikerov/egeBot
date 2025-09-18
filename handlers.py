# handlers.py

import time
import contextlib
import os
from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from datetime import datetime

import keyboards as kb
import database as db
import ai_processing
import robokassa_api
import google_sheets_api as gs
from config import ADMIN_PASSWORD, SUPER_ADMIN_ID
from text_manager import get_text
from price_manager import load_prices, save_prices

router = Router()

# Классы состояний
class UserState(StatesGroup):
    waiting_for_voice = State()
    waiting_for_payment_check = State()

class AdminState(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()

# --- Вспомогательные функции ---
async def is_admin(user_id: int) -> bool:
    admins = await db.get_admins()
    return user_id in admins

async def get_user_status_text(user_id: int) -> str:
    if await is_admin(user_id):
        return get_text('status_admin')
    
    is_subscribed, end_date = await db.check_subscription(user_id)
    if is_subscribed:
        if end_date and end_date != "admin":
            formatted_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
            return get_text('status_subscribed', end_date=formatted_date)
        return get_text('status_subscribed_no_date')

    tasks_info = await db.get_available_tasks(user_id)
    if tasks_info['trials_left'] > 0:
        return get_text('status_trial', trials_left=tasks_info['trials_left'])
    else:
        return get_text('status_no_tasks')

# --- Обработчики основного меню и команд ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username)
    status_text = await get_user_status_text(message.from_user.id)
    await message.answer(
        get_text('start', status_text=status_text),
        reply_markup=kb.main_menu_keyboard()
    )

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    status_text = await get_user_status_text(callback.from_user.id)
    text = get_text('start', status_text=status_text)
    keyboard = kb.main_menu_keyboard()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# --- ОБРАБОТЧИК ДЛЯ WEB APP ---
@router.message(Command("webapp"))
async def cmd_webapp(message: Message):
    # ВАЖНО: Замените на реальную HTTPS-ссылку на ваше веб-приложение
    WEB_APP_URL = "https://almikerov.ru/ege-speaking-simulator/"

    await message.answer(
        "Нажмите кнопку ниже, чтобы запустить тренажер!",
        reply_markup=kb.web_app_keyboard(WEB_APP_URL)
    )

# --- Раздел "Информация" ---
@router.callback_query(F.data == "show_info")
async def show_info_menu(callback: CallbackQuery):
    status_text = await get_user_status_text(callback.from_user.id)
    await callback.message.edit_text(
        get_text('info_text', status_text=status_text),
        reply_markup=kb.info_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "show_offer")
async def show_offer_text(callback: CallbackQuery):
    try:
        offer_document = FSInputFile("offer.docx")
        await callback.message.delete()
        await callback.message.answer_document(
            offer_document,
            caption="📜 Публичная оферта",
            reply_markup=kb.back_to_main_menu_keyboard()
        )
    except FileNotFoundError:
        await callback.answer(get_text('offer_unavailable'), show_alert=True)

# --- Раздел "Подписка и оплата" ---
@router.callback_query(F.data == "show_subscribe_options")
async def show_subscribe_menu(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == UserState.waiting_for_payment_check:
        await state.clear()
        
    prices = load_prices()
    await callback.message.edit_text(
        get_text('subscribe_prompt'),
        reply_markup=kb.subscribe_menu_keyboard(prices)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    tariff = callback.data.split("_")[1]
    prices = load_prices()
    amount = prices.get(tariff)
    if not amount: return await callback.answer("Тариф не найден.", show_alert=True)

    invoice_id = int(f"{user_id}{int(time.time())}")
    payment_link = robokassa_api.generate_payment_link(user_id, amount, invoice_id)
    
    await db.add_pending_payment(invoice_id, user_id, tariff, amount)
    await state.update_data(invoice_id=invoice_id)
    await state.set_state(UserState.waiting_for_payment_check)

    await callback.message.edit_text(
        get_text('buy_prompt', tariff=tariff, amount=amount),
        reply_markup=kb.payment_keyboard(payment_link, amount)
    )
    await callback.answer()

@router.callback_query(F.data == "check_robokassa_payment", UserState.waiting_for_payment_check)
async def check_robokassa_payment_handler(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    invoice_id = state_data.get('invoice_id')

    if not invoice_id:
        await callback.answer("Ошибка: сессия проверки истекла. Пожалуйста, выберите тариф заново.", show_alert=True)
        await show_subscribe_menu(callback, state)
        return

    payment_data = await db.get_pending_payment(invoice_id)
    if not payment_data:
        await callback.answer("Ошибка: не удалось найти счет. Пожалуйста, выберите тариф заново.", show_alert=True)
        await show_subscribe_menu(callback, state)
        return

    user_id, tariff, _ = payment_data
    await callback.answer(get_text('payment_check_started'), show_alert=False)
    is_paid = await robokassa_api.check_payment(invoice_id)

    if is_paid:
        await state.clear()
        await db.remove_pending_payment(invoice_id)
        
        if tariff in ["week", "month"]:
            days = 7 if tariff == "week" else 30
            await db.set_subscription(user_id, days)
            await callback.message.edit_text(
                get_text('payment_success_subscription', days=days),
                reply_markup=kb.main_menu_keyboard()
            )
        elif tariff == "single":
            await db.add_single_tasks(user_id, 1)
            await callback.message.edit_text(
                get_text('payment_success_single'),
                reply_markup=kb.main_menu_keyboard()
            )
    else:
        await callback.message.edit_text(
            get_text('payment_failed'),
            reply_markup=kb.payment_failed_keyboard()
        )

# --- ЛОГИКА ПОЛУЧЕНИЯ И ПРОВЕРКИ ЗАДАНИЙ ---
@router.callback_query(F.data == "get_task")
async def get_task_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    tasks_info = await db.get_available_tasks(user_id)
    prices = load_prices()

    if not (tasks_info["is_subscribed"] or tasks_info["trials_left"] > 0 or tasks_info["single_left"] > 0):
        await callback.message.edit_text(
            get_text('no_tasks_left'),
            reply_markup=kb.subscribe_menu_keyboard(prices)
        )
        await callback.answer()
        return

    sheet_titles = await gs.get_sheet_titles()
    if not sheet_titles:
        await callback.answer("Не удалось загрузить типы заданий. Попробуйте позже.", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите тип задания:",
        reply_markup=kb.task_type_keyboard(sheet_titles)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_task_"))
async def task_type_selected_handler(callback: CallbackQuery, state: FSMContext):
    sheet_title = callback.data[len("select_task_"):]
    await callback.message.edit_text("🔄 Загружаю ваше задание, пожалуйста, подождите...")

    prompt, task_data = await gs.get_task_from_sheet(sheet_title)

    if not prompt or not task_data:
        await callback.message.edit_text("Не удалось загрузить задание. Возможно, лист пуст. Попробуйте другой.", reply_markup=kb.back_to_main_menu_keyboard())
        await callback.answer()
        return

    await db.use_task(callback.from_user.id)
    await state.update_data(
        current_task_text=task_data['task_text'],
        current_prompt=prompt
    )
    await state.set_state(UserState.waiting_for_voice)

    task_id_text = f"<i>(ID на ФИПИ: {task_data['id']})</i>"
    full_task_text = f"<b>Ваше задание:</b>\n\n<blockquote>{task_data['task_text']}</blockquote>\n{task_id_text}\n\n<i>Запишите и отправьте свой ответ в виде голосового сообщения.</i>"

    if task_data.get('image1'):
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=task_data['image1'],
                caption=full_task_text,
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            print(f"Ошибка отправки фото: {e}. Отправляю текст.")
            await callback.message.answer(full_task_text, parse_mode="HTML")
    else:
        await callback.message.edit_text(full_task_text, parse_mode="HTML")
    await callback.answer()

@router.message(UserState.waiting_for_voice, F.voice)
async def voice_message_handler(message: Message, state: FSMContext):
    await message.answer(get_text('voice_accepted'))
    
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    
    try:
        voice_file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(voice_file_info.file_path, voice_ogg_path)
        
        user_data = await state.get_data()
        task_text = user_data.get('current_task_text', 'Задание не найдено.')
        prompt = user_data.get('current_prompt', 'Промпт не найден.')

        review = await ai_processing.get_ai_review(prompt, task_text, voice_ogg_path)
        
        await message.answer(
            f"📝 <b>Ваш разбор ответа:</b>\n\n{review}",
            parse_mode="HTML",
            reply_markup=kb.main_menu_keyboard()
        )
    finally:
        await state.clear()
        if os.path.exists(voice_ogg_path):
            os.remove(voice_ogg_path)

@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))

# --- Админ-панель ---
@router.message(Command(ADMIN_PASSWORD))
async def admin_login(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        await state.clear()
        await message.answer(get_text('admin_welcome'), reply_markup=kb.admin_menu_keyboard())
    else:
        await message.answer("Неверная команда или недостаточно прав.")

@router.callback_query(F.data == "admin_menu")
async def show_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(get_text('admin_welcome'), reply_markup=kb.admin_menu_keyboard())
    await callback.answer()

# --- Админ-панель: Цены ---
@router.callback_query(F.data == "admin_edit_prices")
async def admin_edit_prices_start(callback: CallbackQuery):
    prices = load_prices()
    text = (f"Текущие цены:\n"
            f"Неделя: {prices.get('week', 'N/A')} RUB\n"
            f"Месяц: {prices.get('month', 'N/A')} RUB\n"
            f"1 задание: {prices.get('single', 'N/A')} RUB\n\n"
            f"Какую цену вы хотите изменить?")
    await callback.message.edit_text(text, reply_markup=kb.edit_prices_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("edit_price_"))
async def admin_select_price_to_edit(callback: CallbackQuery, state: FSMContext):
    tariff = callback.data.split("_")[2]
    await state.update_data(tariff_to_edit=tariff)
    await callback.message.edit_text(f"Введите новую цену для тарифа '{tariff}' (только цифры):")
    await state.set_state(AdminState.waiting_for_new_price)
    await callback.answer()

@router.message(AdminState.waiting_for_new_price, F.text)
async def admin_receive_new_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Ошибка. Пожалуйста, введите только цифры. Попробуйте еще раз.")
        return

    new_price = int(message.text)
    user_data = await state.get_data()
    tariff = user_data.get('tariff_to_edit')

    prices = load_prices()
    prices[tariff] = new_price
    save_prices(prices)

    await message.answer(f"Цена для тарифа '{tariff}' успешно изменена на {new_price} RUB.", reply_markup=kb.admin_menu_keyboard())
    await state.clear()

# --- Админ-панель: Управление администраторами ---
@router.callback_query(F.data == "admin_manage_admins")
async def admin_management_menu(callback: CallbackQuery):
    await callback.message.edit_text("Меню управления администраторами:", reply_markup=kb.admin_management_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_view_admins")
async def view_admins(callback: CallbackQuery):
    admins_ids = await db.get_admins()
    text_lines = ["<b>Список администраторов:</b>"]
    
    for admin_id in admins_ids:
        try:
            chat = await callback.bot.get_chat(admin_id)
            display_name = chat.full_name or chat.username or f"User {admin_id}"
            line = f'• <a href="tg://user?id={admin_id}">{display_name}</a> (<code>{admin_id}</code>)'
        except Exception:
            line = f'• <a href="tg://user?id={admin_id}">User {admin_id}</a> (ID не найден)'
            
        if admin_id == SUPER_ADMIN_ID:
            line += " (⭐ Супер-админ)"
        text_lines.append(line)
        
    await callback.message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=kb.back_to_admins_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_admin_id_to_add)
    await callback.message.edit_text(get_text('admin_add_prompt'), reply_markup=kb.back_to_admins_menu_keyboard())
    await callback.answer()

@router.message(AdminState.waiting_for_admin_id_to_add, F.text)
async def add_admin_finish(message: Message, state: FSMContext):
    user_input = message.text.strip()
    admin_id = None
    
    if user_input.isdigit():
        admin_id = int(user_input)
    elif user_input.startswith('@'):
        username = user_input[1:]
        user_data = await db.get_user_by_username(username)
        if user_data:
            admin_id = user_data[0]
        else:
            await message.answer(f"Пользователь @{username} не найден. Попросите его запустить бота.")
            return
    else:
        await message.answer("Неверный формат. Пришлите ID (цифры) или @username.")
        return

    if admin_id:
        await db.add_admin(admin_id)
        await state.clear()
        await message.answer(get_text('admin_add_success', id=admin_id), reply_markup=kb.admin_management_keyboard())

@router.callback_query(F.data == "admin_remove_admin")
async def remove_admin_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_admin_id_to_remove)
    await callback.message.edit_text(get_text('admin_remove_prompt'), reply_markup=kb.back_to_admins_menu_keyboard())
    await callback.answer()

@router.message(AdminState.waiting_for_admin_id_to_remove, F.text)
async def remove_admin_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return

    admin_id = int(message.text)
    if admin_id == SUPER_ADMIN_ID:
        await message.answer(get_text('admin_remove_super_admin_error'), reply_markup=kb.admin_management_keyboard())
        await state.clear()
        return

    await db.remove_admin(admin_id)
    await state.clear()
    await message.answer(get_text('admin_remove_success', id=admin_id), reply_markup=kb.admin_management_keyboard())

# --- Админ-панель: Пользователи ---
@router.callback_query(F.data == "admin_view_subscribed")
async def view_subscribed_users(callback: CallbackQuery):
    users = await db.get_subscribed_users()
    if not users:
        text = "Нет пользователей с активной подпиской."
    else:
        text = "<b>Пользователи с активной подпиской:</b>\n\n"
        for user_id, username, end_date_str in users:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
            try:
                chat = await callback.bot.get_chat(user_id)
                display_name = chat.full_name or chat.username or f"User {user_id}"
            except Exception:
                display_name = username or f"User {user_id}"

            text += f'• <a href="tg://user?id={user_id}">{display_name}</a> (<code>{user_id}</code>)\n'
            text += f"  <b>Подписка до:</b> {end_date}\n\n"
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb.back_to_admin_menu_keyboard())
    await callback.answer()