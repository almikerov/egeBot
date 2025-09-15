# handlers.py

import random
import time
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from datetime import datetime

import keyboards as kb
import database as db
import ai_processing
import robokassa_api
from config import PRICES, ADMIN_PASSWORD, ADMIN_IDS
from text_manager import get_text

router = Router()

EGE_TASKS = [
    "Describe a photo of your recent holiday.", "What are the pros and cons of distance learning?",
    "Tell me about your favorite book and why you recommend it.", "What job would you like to have in the future? Why?"
]

class UserState(StatesGroup):
    waiting_for_voice = State()

class AdminState(StatesGroup):
    waiting_for_new_prompt = State()

# --- Вспомогательная функция для получения статуса пользователя ---
async def get_user_status_text(user_id: int) -> str:
    """Возвращает текстовое описание статуса пользователя."""
    is_subscribed, end_date = await db.check_subscription(user_id)
    if is_subscribed:
        formatted_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        return get_text('status_subscribed', end_date=formatted_date)

    tasks_info = await db.get_available_tasks(user_id)
    if tasks_info['trials_left'] > 0:
        return get_text('status_trial', trials_left=tasks_info['trials_left'])
    else:
        return get_text('status_no_tasks')

# --- Обработчики основного меню ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start, открывает главное меню."""
    await db.add_user(message.from_user.id, message.from_user.username)
    status_text = await get_user_status_text(message.from_user.id)
    await message.answer(
        get_text('start', status_text=status_text),
        reply_markup=kb.main_menu_keyboard()
    )

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Показывает главное меню при нажатии на кнопку 'Назад'."""
    status_text = await get_user_status_text(callback.from_user.id)
    await callback.message.edit_text(
        get_text('start', status_text=status_text),
        reply_markup=kb.main_menu_keyboard()
    )
    await callback.answer()

# --- Раздел "Информация" ---

@router.callback_query(F.data == "show_info")
async def show_info_menu(callback: CallbackQuery):
    """Показывает меню 'Информация'."""
    status_text = await get_user_status_text(callback.from_user.id)
    await callback.message.edit_text(
        get_text('info_text', status_text=status_text),
        reply_markup=kb.info_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "show_offer")
async def show_offer_text(callback: CallbackQuery):
    """Показывает текст публичной оферты."""
    try:
        with open("offer.txt", "r", encoding="utf-8") as f:
            offer_content = f.read()
            await callback.message.edit_text(
                get_text('offer_text', offer_text=offer_content),
                reply_markup=kb.back_to_main_menu_keyboard()
            )
    except FileNotFoundError:
        await callback.message.edit_text(
            get_text('offer_unavailable'),
            reply_markup=kb.back_to_main_menu_keyboard()
        )
    await callback.answer()

# --- Раздел "Подписка и оплата" ---

@router.callback_query(F.data == "show_subscribe_options")
async def show_subscribe_menu(callback: CallbackQuery):
    """Показывает меню выбора тарифов."""
    await callback.message.edit_text(
        get_text('subscribe_prompt'),
        reply_markup=kb.subscribe_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    tariff = callback.data.split("_")[1]
    amount = PRICES.get(tariff)
    if not amount: return await callback.answer("Тариф не найден.", show_alert=True)

    invoice_id = int(f"{user_id}{int(time.time())}")
    payment_link = robokassa_api.generate_payment_link(user_id, amount, invoice_id)
    await state.update_data(invoice_id=invoice_id, tariff=tariff)

    payment_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"💳 Оплатить {amount} RUB", url=payment_link)],
        [types.InlineKeyboardButton(text="✅ Я оплатил, проверить", callback_data="check_robokassa_payment")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="show_subscribe_options")]
    ])

    await callback.message.edit_text(get_text('buy_prompt', tariff=tariff), reply_markup=payment_kb)
    await callback.answer()

@router.callback_query(F.data == "check_robokassa_payment")
async def check_robokassa_payment_handler(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    invoice_id, tariff = user_data.get('invoice_id'), user_data.get('tariff')
    if not all([invoice_id, tariff]):
        await callback.answer("Ошибка: не удалось найти счет. Пожалуйста, выберите тариф заново.", show_alert=True)
        return

    await callback.message.edit_text("⏳ Проверяем статус платежа...")
    
    is_paid = await robokassa_api.check_payment(invoice_id)

    if is_paid:
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
        await state.clear()
    else:
        failed_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Попробовать еще раз", callback_data="check_robokassa_payment")],
            [types.InlineKeyboardButton(text="⬅️ Выбрать другой тариф", callback_data="show_subscribe_options")]
        ])
        await callback.message.edit_text(
            get_text('payment_failed'),
            reply_markup=failed_kb
        )
    await callback.answer()

# --- Основная логика получения и проверки заданий ---

@router.callback_query(F.data == "get_task")
async def get_task_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_subscribed, _ = await db.check_subscription(user_id)
    tasks_info = await db.get_available_tasks(user_id)

    if is_subscribed or tasks_info["trials_left"] > 0 or tasks_info["single_left"] > 0:
        await give_task(callback, state, tasks_info)
    else:
        await callback.message.edit_text(
            get_text('no_tasks_left'),
            reply_markup=kb.subscribe_menu_keyboard()
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
        # Получаем актуальное количество попыток ПОСЛЕ списания
        updated_tasks_info = await db.get_available_tasks(callback.from_user.id)
        if tasks_info["trials_left"] > 0:
            message_text = get_text('get_task_trial', trials_left=updated_tasks_info['trials_left'], task=task)
        else:
            message_text = get_text('get_task_single', single_left=updated_tasks_info['single_left'], task=task)

    await callback.message.edit_text(message_text, parse_mode="HTML")

@router.message(UserState.waiting_for_voice, F.voice)
async def voice_message_handler(message: Message, state: FSMContext):
    await message.answer(get_text('voice_accepted'))
    voice_file_info = await message.bot.get_file(message.voice.file_id)
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    await message.bot.download_file(voice_file_info.file_path, voice_ogg_path)
    recognized_text = await ai_processing.recognize_speech(voice_ogg_path)

    if "Ошибка:" in recognized_text:
        await message.answer(recognized_text, reply_markup=kb.main_menu_keyboard())
        await state.clear()
        return

    user_data = await state.get_data()
    task = user_data.get('current_task', 'Не найдено.')
    review = await ai_processing.get_ai_review(task, recognized_text)
    await message.answer(
        f"📝 <b>Ваш разбор ответа:</b>\n\n{review}",
        parse_mode="HTML",
        reply_markup=kb.main_menu_keyboard()
    )
    await state.clear()

@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))

# --- Админ-панель (без изменений) ---

@router.message(Command(ADMIN_PASSWORD))
async def admin_login(message: Message):
    if message.from_user.id in ADMIN_IDS:
        admin_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Изменить промпт", callback_data="admin_edit_prompt")]
        ])
        await message.answer(get_text('admin_welcome'), reply_markup=admin_kb)
    else:
        await message.answer("Неверная команда или недостаточно прав.")

@router.callback_query(F.data == "admin_edit_prompt")
async def admin_edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(get_text('admin_prompt_request'))
    await state.set_state(AdminState.waiting_for_new_prompt)
    await callback.answer()

@router.message(AdminState.waiting_for_new_prompt)
async def admin_edit_prompt_finish(message: Message, state: FSMContext):
    try:
        with open("prompt.txt", "w", encoding="utf-8") as f:
            f.write(message.text)
        await message.answer(get_text('admin_prompt_success'))
    except Exception as e:
        await message.answer(get_text('admin_prompt_fail', e=e))
    await state.clear()