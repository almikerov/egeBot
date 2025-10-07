# handlers.py

import asyncio
import time
import contextlib
import os
import re
from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from datetime import datetime

import keyboards as kb
import database as db
import ai_processing
import robokassa_api
import task_manager as tm
from config import ADMIN_PASSWORD, SUPER_ADMIN_ID
from text_manager import get_text
from price_manager import load_prices, save_prices

router = Router()

# Классы состояний
class UserState(StatesGroup):
    waiting_for_voice = State()
    waiting_for_payment_check = State()
    waiting_for_task_id = State()

class AdminState(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()
    waiting_for_new_prompt = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def split_message(text: str, chunk_size: int = 4000):
    """Разбивает длинный текст на части, не нарушая Markdown."""
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
    """Экранирует специальные символы для MarkdownV2."""
    if not isinstance(text, str):
        return ''
    escape_chars = r'_*[]()`>#+-.!{}'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def clean_ai_response(text: str) -> str:
    """Преобразует Markdown от AI в совместимый с Telegram MarkdownV2."""
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
    await db.use_task(message.from_user.id)
    
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

@router.callback_query(F.data == "get_task")
async def get_task_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_user_can_get_task(callback.from_user.id, callback):
        return
        
    task_types = tm.get_task_types()
    if not task_types:
        await callback.answer("Не удалось загрузить типы заданий. Возможно, файл с заданиями пуст.", show_alert=True)
        return
        
    await callback.message.edit_text(
        "Выберите тип задания:",
        reply_markup=kb.task_type_keyboard(task_types)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_task_"))
async def task_type_selected_handler(callback: CallbackQuery, state: FSMContext):
    task_type = callback.data[len("select_task_"):]
    await callback.message.edit_text("🔄 Загружаю ваше задание...")
    prompt, task_data = tm.get_random_task(task_type)
    if not prompt or not task_data:
        await callback.message.edit_text("Не удалось загрузить задание этого типа.", reply_markup=kb.back_to_main_menu_keyboard())
        await callback.answer()
        return
    await send_task(callback, state, task_data, prompt)
    await callback.answer()

@router.message(UserState.waiting_for_voice, F.voice)
async def voice_message_handler(message: Message, state: FSMContext):
    user_data = await state.get_data()
    time_limit = user_data.get('time_limit')

    if time_limit and message.voice.duration > time_limit:
        await message.answer(get_text('voice_too_long', limit=time_limit, duration=message.voice.duration))
        return

    await message.answer(get_text('voice_accepted'))
    voice_ogg_path = f"voice_{message.from_user.id}.ogg"
    review = ""
    try:
        voice_file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(voice_file_info.file_path, voice_ogg_path)
        
        task_text = user_data.get('current_task_text', 'Задание не найдено.')
        prompt = user_data.get('current_prompt', 'Промпт не найден.')
        review = await ai_processing.get_ai_review(prompt, task_text, voice_ogg_path)
        
        cleaned_review = clean_ai_response(review)
        escaped_review = escape_markdown(cleaned_review)
        
        await message.answer("📝 *Ваш разбор ответа:*", parse_mode="MarkdownV2")
        
        for chunk in split_message(escaped_review):
            await message.answer(chunk, parse_mode="MarkdownV2")
            await asyncio.sleep(0.5)

        await send_main_menu(message, message.from_user.id)
        
    except TelegramBadRequest as e:
        print(f"ОШИБКА: Не удалось отправить отформатированный ответ Gemini: {e}.")
        print("--- AI Response (Raw, Caused Error) ---")
        print(review)
        print("---------------------------------------")
        
        if "message is too long" in str(e).lower():
            await message.answer(
                "⚠️ *Ошибка:* Ответ от AI получился слишком большим, даже для отправки по частям. Попробуйте дать более короткий ответ.",
                parse_mode="MarkdownV2"
            )
        else:
            await message.answer(
                f"📝 Ваш разбор ответа (ошибка форматирования):\n\n{review}"
            )
        await send_main_menu(message, message.from_user.id)
        
    finally:
        await state.clear()
        if os.path.exists(voice_ogg_path):
            os.remove(voice_ogg_path)

@router.message(UserState.waiting_for_voice)
async def incorrect_message_handler(message: Message):
    await message.answer(get_text('voice_error'))
    
# --- АДМИН-ПАНЕЛЬ ---

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

# --- РЕДАКТИРОВАНИЕ ПРОМПТОВ (НОВЫЙ БЛОК) ---

@router.callback_query(F.data == "admin_edit_prompts")
async def admin_edit_prompts_start(callback: CallbackQuery):
    task_types = tm.get_task_types()
    if not task_types:
        await callback.answer("Не найдены типы заданий для редактирования.", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите, для какого типа заданий вы хотите изменить промпт:",
        reply_markup=kb.prompt_types_keyboard(task_types)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_prompt_"))
async def admin_select_prompt_to_edit(callback: CallbackQuery, state: FSMContext):
    task_type = callback.data[len("edit_prompt_"):]
    current_prompt = tm.get_prompt(task_type)
    
    await state.update_data(prompt_task_type=task_type)
    await state.set_state(AdminState.waiting_for_new_prompt)
    
    # Отправляем сообщение в несколько частей, если оно длинное
    header = f"Текущий промпт для *{escape_markdown(task_type)}*:\n\n"
    prompt_body = f"```\n{escape_markdown(current_prompt)}\n```\n\n"
    footer = "Пришлите новый текст промпта."
    
    full_message = header + prompt_body + footer
    
    try:
        await callback.message.edit_text(full_message, parse_mode="MarkdownV2")
    except TelegramBadRequest:
        # Если сообщение слишком длинное даже для одного блока
        await callback.message.edit_text(header, parse_mode="MarkdownV2")
        for chunk in split_message(prompt_body):
            await callback.message.answer(chunk, parse_mode="MarkdownV2")
        await callback.message.answer(footer)

    await callback.answer()

@router.message(AdminState.waiting_for_new_prompt, F.text)
async def admin_receive_new_prompt(message: Message, state: FSMContext):
    user_data = await state.get_data()
    task_type = user_data.get('prompt_task_type')
    new_prompt_text = message.text

    if tm.save_prompt(task_type, new_prompt_text):
        await message.answer(
            f"✅ Промпт для типа *{escape_markdown(task_type)}* успешно обновлен!",
            parse_mode="MarkdownV2",
            reply_markup=kb.admin_menu_keyboard()
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при сохранении промпта.",
            reply_markup=kb.admin_menu_keyboard()
        )
    
    await state.clear()

# --- ОСТАЛЬНЫЕ АДМИН-ФУНКЦИИ ---
# ... (здесь идет остальной код из handlers.py: редактирование цен, управление админами и т.д.)
# Убедитесь, что вы скопировали и его.