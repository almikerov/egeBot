# handlers.py

import asyncio
import contextlib
import os
import re
from datetime import datetime
from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto

import keyboards as kb
import database as db
import ai_processing
import robokassa_api
import task_manager as tm
from config import ADMIN_PASSWORD, SUPER_ADMIN_ID
from text_manager import get_text
from price_manager import load_prices, save_prices

router = Router()

class UserState(StatesGroup):
    waiting_for_voice = State()
    waiting_for_payment_check = State()
    waiting_for_task_id = State()

class AdminState(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()

# ... (все вспомогательные функции остаются без изменений) ...
def split_message(text: str, chunk_size: int = 4000):
    if len(text) <= chunk_size:
        yield text
        return
    last_cut = 0
    while last_cut < len(text):
        next_cut = last_cut + chunk_size
        if next_cut >= len(text):
            yield text[last_cut:]
            break
        cut_pos = text.rfind('\n', last_cut, next_cut)
        if cut_pos == -1:
            cut_pos = text.rfind(' ', last_cut, next_cut)
        if cut_pos == -1 or cut_pos <= last_cut:
            cut_pos = next_cut
        yield text[last_cut:cut_pos]
        last_cut = cut_pos

def escape_markdown(text: str) -> str:
    if not isinstance(text, str):
        return ''
    escape_chars = r'_*[]()`>#+-.!{}'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def clean_ai_response(text: str) -> str:
    if not isinstance(text, str):
        return ''
    cleaned_text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    return cleaned_text

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

async def send_main_menu(message: types.Message, user_id: int):
    status_text = await get_user_status_text(user_id)
    await message.answer(
        get_text('start', status_text=status_text),
        reply_markup=kb.main_menu_keyboard()
    )

async def send_task(message: types.Message, state: FSMContext, task_data: dict, prompt: str):
    await state.update_data(
        current_task_text=task_data.get('task_text'),
        current_prompt=prompt,
        time_limit=task_data.get('time_limit')
    )
    await state.set_state(UserState.waiting_for_voice)
    cleaned_task_text = clean_ai_response(task_data.get('task_text', ''))
    escaped_text = escape_markdown(cleaned_task_text)
    quoted_task_text = "\n".join([f"> {line}" for line in escaped_text.split('\n')])
    safe_task_id = escape_markdown(str(task_data.get('id', 'N/A')))
    task_id_text = f"_\\(ID: {safe_task_id}\\)_"
    instruction_text = "_Запишите и отправьте свой ответ в виде голосового сообщения\\._"
    full_task_text = f"*Ваше задание:*\n\n{quoted_task_text}\n\n{task_id_text}\n\n{instruction_text}"
    if isinstance(message, CallbackQuery):
        message = message.message
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()
    image1 = task_data.get('image1')
    image2 = task_data.get('image2')
    try:
        if image1 and image2:
            media = [InputMediaPhoto(media=image1), InputMediaPhoto(media=image2)]
            await message.answer_media_group(media)
        elif image1:
            await message.answer_photo(photo=image1)
        await message.answer(full_task_text, parse_mode="MarkdownV2")
    except TelegramBadRequest as e:
        print(f"Ошибка отправки медиа: {e}. Отправляю только текст.")
        await message.answer(full_task_text, parse_mode="MarkdownV2")

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username)
    await send_main_menu(message, message.from_user.id)

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.delete()
    await send_main_menu(callback.message, callback.from_user.id)
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
        
@router.callback_query(F.data == "show_subscribe_options")
async def show_subscribe_menu(callback: CallbackQuery, state: FSMContext):
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
    if not amount:
        return await callback.answer("Тариф не найден.", show_alert=True)

    invoice_id = await db.add_pending_payment(user_id, tariff, amount)
    if not invoice_id:
        return await callback.answer("Не удалось создать счет.", show_alert=True)

    # Функция сама выберет нужный пароль
    payment_link = robokassa_api.generate_payment_link(
        amount=amount,
        invoice_id=invoice_id
    )

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
        await callback.answer("Сессия проверки истекла.", show_alert=True)
        return await show_subscribe_menu(callback, state)

    payment_data = await db.get_pending_payment(invoice_id)
    if not payment_data:
        await callback.answer("Счет не найден.", show_alert=True)
        return await show_subscribe_menu(callback, state)

    user_id, tariff, _ = payment_data
    await callback.answer(get_text('payment_check_started'), show_alert=False)

    # Функция сама выберет нужный пароль
    is_paid = await robokassa_api.check_payment(invoice_id=invoice_id)
    
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.delete()

    if is_paid:
        await state.clear()
        await db.remove_pending_payment(invoice_id)
        if tariff in ["week", "month"]:
            days = 7 if tariff == "week" else 30
            await db.set_subscription(user_id, days)
            await callback.message.answer(get_text('payment_success_subscription', days=days))
        elif tariff == "single":
            await db.add_single_tasks(user_id, 1)
            await callback.message.answer(get_text('payment_success_single'))
        await send_main_menu(callback.message, user_id)
    else:
        await callback.message.answer(
            get_text('payment_failed'),
            reply_markup=kb.payment_failed_keyboard()
        )

# ... (остальной код handlers.py без изменений) ...
async def check_user_can_get_task(user_id: int, message: types.Message) -> bool:
    tasks_info = await db.get_available_tasks(user_id)
    if not (tasks_info["is_subscribed"] or tasks_info["trials_left"] > 0 or tasks_info["single_left"] > 0):
        prices = load_prices()
        if isinstance(message, CallbackQuery):
            await message.message.edit_text(get_text('no_tasks_left'), reply_markup=kb.subscribe_menu_keyboard(prices))
            await message.answer()
        else:
            await message.answer(get_text('no_tasks_left'), reply_markup=kb.subscribe_menu_keyboard(prices))
        return False
    return True

@router.callback_query(F.data == "get_task")
async def get_task_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_user_can_get_task(callback.from_user.id, callback):
        return
    task_types = tm.get_task_types()
    if not task_types:
        await callback.answer("Не удалось загрузить типы заданий.", show_alert=True)
        return
    await callback.message.edit_text("Выберите тип задания:", reply_markup=kb.task_type_keyboard(task_types))
    await callback.answer()

@router.callback_query(F.data.startswith("select_task_"))
async def task_type_selected_handler(callback: CallbackQuery, state: FSMContext):
    task_type = callback.data[len("select_task_"):]
    await callback.message.edit_text("🔄 Загружаю ваше задание...")
    prompt, task_data = tm.get_random_task(task_type)
    if not prompt or not task_data:
        await callback.message.edit_text("Не удалось загрузить задание.", reply_markup=kb.back_to_main_menu_keyboard())
        return
    await send_task(callback, state, task_data, prompt)

@router.callback_query(F.data == "get_task_by_id_prompt")
async def get_task_by_id_prompt_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_task_id)
    await callback.message.edit_text(get_text('get_task_by_id_prompt'))
    await callback.answer()

@router.message(UserState.waiting_for_task_id, F.text)
async def get_task_by_id_finish_handler(message: Message, state: FSMContext):
    task_id = message.text.strip()
    if not await check_user_can_get_task(message.from_user.id, message):
        await state.clear()
        return
    prompt, task_data = tm.get_task_by_id(task_id)
    if not task_data:
        await message.answer(get_text('task_not_found'), reply_markup=kb.back_to_main_menu_keyboard())
        await state.clear()
        return
    await send_task(message, state, task_data, prompt)

@router.message(UserState.waiting_for_voice, F.voice)
async def voice_message_handler(message: Message, state: FSMContext):
    user_data = await state.get_data()
    time_limit = user_data.get('time_limit')
    if time_limit and message.voice.duration > time_limit:
        await message.answer(get_text('voice_too_long', limit=time_limit, duration=message.voice.duration))
        return
    await message.answer(get_text('voice_accepted'))
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    try:
        voice_file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(voice_file_info.file_path, voice_ogg_path)
        task_text = user_data.get('current_task_text', 'Задание не найдено.')
        prompt = user_data.get('current_prompt', 'Промпт не найден.')
        review = await ai_processing.get_ai_review(prompt, task_text, voice_ogg_path)
        if "Бот сейчас перегружен" in review:
            await message.answer(review)
        else:
            await db.use_task(message.from_user.id)
            cleaned_review = clean_ai_response(review)
            await message.answer("📝 *Ваш разбор ответа:*", parse_mode="MarkdownV2")
            try:
                escaped_review = escape_markdown(cleaned_review)
                for chunk in split_message(escaped_review):
                    await message.answer(chunk, parse_mode="MarkdownV2")
                    await asyncio.sleep(0.5)
            except TelegramBadRequest:
                await message.answer("⚠️ *Ошибка форматирования.* Отправляю как обычный текст:", parse_mode="MarkdownV2")
                for chunk in split_message(review):
                    await message.answer(chunk)
                    await asyncio.sleep(0.5)
        await send_main_menu(message, message.from_user.id)
    finally:
        await state.clear()
        if os.path.exists(voice_ogg_path):
            os.remove(voice_ogg_path)

@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))

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
    await state.set_state(AdminState.waiting_for_new_price)
    await callback.message.edit_text(f"Введите новую цену для тарифа '{tariff}' (только цифры):")
    await callback.answer()

@router.message(AdminState.waiting_for_new_price, F.text)
async def admin_receive_new_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Ошибка. Пожалуйста, введите только цифры.")
        return
    new_price = int(message.text)
    user_data = await state.get_data()
    tariff = user_data.get('tariff_to_edit')
    prices = load_prices()
    prices[tariff] = new_price
    save_prices(prices)
    await state.clear()
    await message.answer(f"Цена для тарифа '{tariff}' успешно изменена на {new_price} RUB.", reply_markup=kb.admin_menu_keyboard())

@router.callback_query(F.data == "admin_manage_admins")
async def admin_management_menu(callback: CallbackQuery):
    await callback.message.edit_text("Меню управления администраторами:", reply_markup=kb.admin_management_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_view_admins")
async def view_admins(callback: CallbackQuery):
    admins_ids = await db.get_admins()
    text_lines = ["*Список администраторов:*"]
    for admin_id in admins_ids:
        try:
            chat = await callback.bot.get_chat(admin_id)
            display_name = escape_markdown(chat.full_name or chat.username or f"User {admin_id}")
            line = f"• [{display_name}](tg://user?id={admin_id}) (`{admin_id}`)"
        except Exception:
            line = f"• [User {admin_id}](tg://user?id={admin_id}) \\(ID не найден\\)"
        if admin_id == SUPER_ADMIN_ID:
            line += " \\(⭐ Супер\\-админ\\)"
        text_lines.append(line)
    await callback.message.edit_text("\n".join(text_lines), parse_mode="MarkdownV2", reply_markup=kb.back_to_admins_menu_keyboard())
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
            await message.answer(f"Пользователь @{username} не найден.")
            return
    else:
        await message.answer("Неверный формат. Пришлите ID или @username.")
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

@router.callback_query(F.data == "admin_view_subscribed")
async def view_subscribed_users(callback: CallbackQuery):
    users = await db.get_subscribed_users()
    if not users:
        text = "Нет пользователей с активной подпиской."
    else:
        text = "*Пользователи с активной подпиской:*\n\n"
        for user_id, username, end_date_str in users:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
            try:
                chat = await callback.bot.get_chat(user_id)
                display_name = escape_markdown(chat.full_name or chat.username or f"User {user_id}")
            except Exception:
                display_name = escape_markdown(username or f"User {user_id}")
            safe_end_date = escape_markdown(end_date)
            text += f"• [{display_name}](tg://user?id={user_id}) (`{user_id}`)\n"
            text += f"  *Подписка до:* {safe_end_date}\n\n"
    await callback.message.edit_text(text, parse_mode='MarkdownV2', reply_markup=kb.back_to_admin_menu_keyboard())
    await callback.answer()

@router.message(F.text)
async def handle_unknown_text(message: Message):
    await message.answer(get_text('unknown_command_instruction'))