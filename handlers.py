# handlers.py

import random
import time
import contextlib
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
    # ИЗМЕНЕНО: Добавляем состояние для ожидания проверки платежа, чтобы хранить invoice_id
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
    # ИЗМЕНЕНО: Проверяем, является ли пользователь админом в первую очередь
    if await is_admin(user_id):
        return get_text('status_admin')
    
    is_subscribed, end_date = await db.check_subscription(user_id)
    if is_subscribed:
        # end_date здесь уже не может быть 'admin'
        formatted_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        return get_text('status_subscribed', end_date=formatted_date)

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

# ... (код show_main_menu, show_info_menu, show_offer_text без изменений)
@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
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
    
    # ИЗМЕНЕНО: Сохраняем информацию о платеже в БД, а не в FSM
    await db.add_pending_payment(invoice_id, user_id, tariff, amount)
    # Сохраняем в состояние только ID счета для последующей проверки
    await state.update_data(invoice_id=invoice_id)
    await state.set_state(UserState.waiting_for_payment_check)

    await callback.message.edit_text(
        get_text('buy_prompt', tariff=tariff),
        reply_markup=kb.payment_keyboard(payment_link, amount)
    )
    await callback.answer()

@router.callback_query(F.data == "check_robokassa_payment", UserState.waiting_for_payment_check)
async def check_robokassa_payment_handler(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    invoice_id = state_data.get('invoice_id')
    
    # ИЗМЕНЕНО: Получаем данные о платеже из БД
    payment_data = await db.get_pending_payment(invoice_id)
    
    if not payment_data:
        await callback.answer("Ошибка: не удалось найти счет. Пожалуйста, выберите тариф заново.", show_alert=True)
        await show_subscribe_menu(callback)
        return

    user_id, tariff, amount = payment_data
    
    await callback.answer("⏳ Проверяем статус платежа...")
    
    is_paid = await robokassa_api.check_payment(invoice_id)

    if is_paid:
        await state.clear()
        # Удаляем счет из БД после успешной оплаты
        await db.remove_pending_payment(invoice_id)
        
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
# ... (код get_task_handler, give_task, voice_message_handler, incorrect_message_handler без изменений)
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
            # ИЗМЕНЕНО: Форматируем дату для вывода
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
            
            try:
                chat = await callback.bot.get_chat(user_id)
                display_name = chat.full_name or chat.username or f"User {user_id}"
            except Exception:
                display_name = username or f"User {user_id}"

            text += f'• <a href="tg://user?id={user_id}">{display_name}</a> (<code>{user_id}</code>)\n'
            # ИЗМЕНЕНО: Отображаем дату окончания подписки
            text += f"  <b>Подписка до:</b> {end_date}\n\n"
    
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb.back_to_admin_menu_keyboard())
    await callback.answer()

# --- Остальной код handlers.py без изменений ---
# ...