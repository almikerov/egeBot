# handlers.py

import random
import time
import contextlib
import json
import os # <-- Добавляем импорт для работы с файловой системой
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
from prompt_manager import load_prompt

router = Router()

EGE_TASKS = [
    "Describe a photo of your recent holiday.", "What are the pros and cons of distance learning?",
    "Tell me about your favorite book and why you recommend it.", "What job would you like to have in the future? Why?"
]

class UserState(StatesGroup):
    waiting_for_voice = State()

class AdminState(StatesGroup):
    waiting_for_new_prompt = State()
    waiting_for_new_price = State()
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()

# --- Вспомогательные функции ---
async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    admins = await db.get_admins()
    return user_id in admins

async def get_user_status_text(user_id: int) -> str:
    """Возвращает текстовое описание статуса пользователя."""
    is_subscribed, end_date = await db.check_subscription(user_id)
    if is_subscribed:
        if end_date:
            formatted_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
            return get_text('status_subscribed', end_date=formatted_date)
        return get_text('status_subscribed_no_date')

    tasks_info = await db.get_available_tasks(user_id)
    if tasks_info['trials_left'] > 0:
        return get_text('status_trial', trials_left=tasks_info['trials_left'])
    else:
        return get_text('status_no_tasks')

# --- Обработчики основного меню ---

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start, открывает главное меню."""
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username)
    status_text = await get_user_status_text(message.from_user.id)
    await message.answer(
        get_text('start', status_text=status_text),
        reply_markup=kb.main_menu_keyboard()
    )

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню, обрабатывая разные типы сообщений."""
    await state.clear()
    status_text = await get_user_status_text(callback.from_user.id)
    text = get_text('start', status_text=status_text)
    keyboard = kb.main_menu_keyboard()

    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    await callback.message.delete()
    await callback.message.answer(text, reply_markup=keyboard)
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
async def show_subscribe_menu(callback: CallbackQuery):
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
    await state.update_data(invoice_id=invoice_id, tariff=tariff, amount=amount)

    await callback.message.edit_text(
        get_text('buy_prompt', tariff=tariff, amount=amount),
        reply_markup=kb.payment_keyboard(payment_link, amount)
    )
    await callback.answer()

@router.callback_query(F.data == "check_robokassa_payment")
async def check_robokassa_payment_handler(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    invoice_id, tariff = user_data.get('invoice_id'), user_data.get('tariff')
    if not all([invoice_id, tariff]):
        await callback.answer("Ошибка: не удалось найти счет. Пожалуйста, выберите тариф заново.", show_alert=True)
        return

    await callback.answer("⏳ Проверяем статус платежа...")

    is_paid = await robokassa_api.check_payment(invoice_id)

    if is_paid:
        await state.clear()
        if tariff in ["week", "month"]:
            days = 7 if tariff == "week" else 30
            await db.set_subscription(callback.from_user.id, days)
            await callback.message.edit_text(
                get_text('payment_success_subscription', days=days),
                reply_markup=kb.main_menu_keyboard()
            )
        elif tariff == "single":
            await db.add_single_tasks(callback.from_user.id, 1)
            await callback.message.edit_text(
                get_text('payment_success_single'),
                reply_markup=kb.main_menu_keyboard()
            )
    else:
        await callback.message.edit_text(
            get_text('payment_failed'),
            reply_markup=kb.payment_failed_keyboard()
        )
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
    
    # ИЗМЕНЕНО: Определяем пути к файлам заранее
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    voice_mp3_path = voice_ogg_path.replace(".ogg", ".mp3")

    try:
        # Основная логика обработки
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
        # ИЗМЕНЕНО: Блок finally для гарантированного удаления файлов
        await state.clear() # Очищаем состояние в любом случае
        
        # Удаляем ogg файл, если он существует
        if os.path.exists(voice_ogg_path):
            os.remove(voice_ogg_path)
            print(f"Файл {voice_ogg_path} удален.")
            
        # Удаляем mp3 файл, если он существует
        if os.path.exists(voice_mp3_path):
            os.remove(voice_mp3_path)
            print(f"Файл {voice_mp3_path} удален.")


@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))

# --- Админ-панель ---

@router.message(Command(ADMIN_PASSWORD))
async def admin_login(message: Message):
    if await is_admin(message.from_user.id):
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
    current_prompt = load_prompt()
    text = (
        "Пришлите новый текст промпта. Используйте {task_text} и {user_text} как переменные.\n\n"
        "<b>Текущий промпт для примера:</b>\n"
        f"<pre>{current_prompt}</pre>"
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
    admins = await db.get_admins()
    text = "<b>Список администраторов:</b>\n"
    for admin_id in admins:
        text += f'• <a href="tg://user?id={admin_id}">{admin_id}</a>'
        if admin_id == SUPER_ADMIN_ID:
            text += " (⭐ Супер-админ)"
        text += "\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_admins_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_admin_id_to_add)
    await callback.message.edit_text(get_text('admin_add_prompt'), reply_markup=kb.back_to_admins_menu_keyboard())
    await callback.answer()

@router.message(AdminState.waiting_for_admin_id_to_add, F.text)
async def add_admin_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID пользователя должен быть числом. Попробуйте снова.")
        return
    
    admin_id = int(message.text)
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
            text += f'• <b>ID:</b> <a href="tg://user?id={user_id}">{user_id}</a>\n'
            if username and username != 'None':
                 text += f"  <b>Username:</b> @{username}\n"
            text += f"  <b>До:</b> {end_date}\n\n"
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb.back_to_admin_menu_keyboard())
    await callback.answer()