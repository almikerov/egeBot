# handlers.py

import random
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
from config import ADMIN_PASSWORD, SUPER_ADMIN_ID
from text_manager import get_text
from price_manager import load_prices, save_prices
from prompt_manager import DEFAULT_PROMPT

router = Router()

EGE_TASKS = [
    "Describe a photo of your recent holiday.", "What are the pros and cons of distance learning?",
    "Tell me about your favorite book and why you recommend it.", "What job would you like to have in the future? Why?"
]

class UserState(StatesGroup):
    waiting_for_voice = State()
    waiting_for_payment_check = State()

class AdminState(StatesGroup):
    waiting_for_new_prompt = State()
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
        # Fallback for subscriptions without a date, though unlikely with current logic
        return get_text('status_subscribed_no_date')


    tasks_info = await db.get_available_tasks(user_id)
    if tasks_info['trials_left'] > 0:
        return get_text('status_trial', trials_left=tasks_info['trials_left'])
    else:
        return get_text('status_no_tasks')

# --- Обработчики основного меню ---

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
    await callback.answer()

# --- Раздел "Подписка и оплата" ---

@router.callback_query(F.data == "show_subscribe_options")
async def show_subscribe_menu(callback: CallbackQuery, state: FSMContext):
    # Убедимся, что выходим из состояния ожидания платежа, если пользователь решил выбрать другой тариф
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
        await callback.answer("Ошибка: не удалось найти счет в базе. Пожалуйста, выберите тариф заново.", show_alert=True)
        await show_subscribe_menu(callback, state)
        return

    user_id, tariff, amount = payment_data
    
    await callback.answer("⏳ Проверяем статус платежа...")
    
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
    # Не убираем await callback.answer() - это нормально, если он вызывается несколько раз
    await callback.answer()

# --- Основная логика получения и проверки заданий ---

@router.callback_query(F.data == "get_task")
async def get_task_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_subscribed, _ = await db.check_subscription(user_id)
    tasks_info = await db.get_available_tasks(user_id)
    prices = load_prices()

    if is_subscribed or tasks_info["trials_left"] > 0 or tasks_info["single_left"] > 0:
        await give_task(callback, state, tasks_info)
    else:
        await callback.message.edit_text(
            get_text('no_tasks_left'),
            reply_markup=kb.subscribe_menu_keyboard(prices)
        )
    await callback.answer()

async def give_task(callback: CallbackQuery, state: FSMContext, tasks_info: dict):
    await db.use_task(callback.from_user.id)
    task = random.choice(EGE_TASKS)
    await state.update_data(current_task=task)
    await state.set_state(UserState.waiting_for_voice)

    is_subscribed, _ = await db.check_subscription(callback.from_user.id)

    message_text = ""
    if is_subscribed:
         message_text = get_text('get_task_subscribed', task=task)
    else:
        updated_tasks_info = await db.get_available_tasks(callback.from_user.id)
        if tasks_info["trials_left"] > 0:
            message_text = get_text('get_task_trial', trials_left=updated_tasks_info['trials_left'], task=task)
        else:
            message_text = get_text('get_task_single', single_left=updated_tasks_info['single_left'], task=task)

    await callback.message.edit_text(message_text, parse_mode="HTML")

@router.message(UserState.waiting_for_voice, F.voice)
async def voice_message_handler(message: Message, state: FSMContext):
    await message.answer(get_text('voice_accepted'))
    
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    voice_mp3_path = voice_ogg_path.replace(".ogg", ".mp3")

    try:
        voice_file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(voice_file_info.file_path, voice_ogg_path)
        
        recognized_text = await ai_processing.recognize_speech(voice_ogg_path)

        if "Ошибка:" in recognized_text:
            await message.answer(recognized_text, reply_markup=kb.main_menu_keyboard())
            return

        user_data = await state.get_data()
        task = user_data.get('current_task', 'Не найдено.')
        review = await ai_processing.get_ai_review(task, recognized_text)
        
        await message.answer(
            f"📝 <b>Ваш разбор ответа:</b>\n\n{review}",
            parse_mode="HTML",
            reply_markup=kb.main_menu_keyboard()
        )

    finally:
        await state.clear()
        
        if os.path.exists(voice_ogg_path):
            os.remove(voice_ogg_path)
        if os.path.exists(voice_mp3_path):
            os.remove(voice_mp3_path)


@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))

# --- Админ-панель ---

@router.message(Command(ADMIN_PASSWORD))
async def admin_login(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        await state.clear() # На всякий случай сбрасываем состояние
        await message.answer(get_text('admin_welcome'), reply_markup=kb.admin_menu_keyboard())
    else:
        await message.answer("Неверная команда или недостаточно прав.")

@router.callback_query(F.data == "admin_menu")
async def show_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(get_text('admin_welcome'), reply_markup=kb.admin_menu_keyboard())
    await callback.answer()

# --- Админ-панель: Промпт ---
@router.callback_query(F.data == "admin_view_prompt")
async def admin_view_prompt(callback: CallbackQuery):
    try:
        with open("prompt.txt", "r", encoding="utf-8") as f:
            prompt_text = f.read()
        await callback.message.edit_text(
            f"<b>Текущий промпт:</b>\n\n<pre>{prompt_text}</pre>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_menu_keyboard()
        )
    except FileNotFoundError:
        await callback.message.edit_text("Файл prompt.txt не найден.", reply_markup=kb.back_to_admin_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_edit_prompt")
async def admin_edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    example_prompt = DEFAULT_PROMPT
    text = (
        "Пришлите новый текст промпта. Используйте {task_text} и {user_text} как переменные.\n\n"
        "<b>Дефолтный промпт для примера:</b>\n"
        f"<pre>{example_prompt}</pre>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_admin_menu_keyboard())
    await state.set_state(AdminState.waiting_for_new_prompt)
    await callback.answer()

@router.message(AdminState.waiting_for_new_prompt, F.text)
async def admin_edit_prompt_finish(message: Message, state: FSMContext):
    try:
        with open("prompt.txt", "w", encoding="utf-8") as f:
            f.write(message.text)
        await message.answer(get_text('admin_prompt_success'), reply_markup=kb.admin_menu_keyboard())
    except Exception as e:
        await message.answer(get_text('admin_prompt_fail', e=e), reply_markup=kb.admin_menu_keyboard())
    await state.clear()

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
    user_input = message.text
    admin_id = None
    
    if user_input.isdigit():
        admin_id = int(user_input)
    elif user_input.startswith('@'):
        username = user_input[1:]
        user_data = await db.get_user_by_username(username)
        if user_data:
            admin_id = user_data[0]
        else:
            await message.answer(f"Пользователь @{username} не найден в базе данных. Попросите его сначала запустить бота.")
            return
    else:
        await message.answer("Неверный формат. Пришлите ID пользователя (только цифры) или его @username.")
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
        await message.answer("ID пользователя должен быть числом. Попробуйте снова.")
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
        text = "На данный момент нет пользователей с активной подпиской."
    else:
        text = "<b>Пользователи с активной подпиской:</b>\n\n"
        for user in users:
            user_id, username, end_date_str = user
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