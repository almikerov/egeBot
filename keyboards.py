# keyboards.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PRICES

def main_menu_keyboard():
    """Возвращает клавиатуру главного меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Получить задание", callback_data="get_task")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="show_subscribe_options")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="show_info")]
    ])
    return keyboard

def subscribe_menu_keyboard():
    """Возвращает клавиатуру для выбора тарифа подписки."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Неделя - {PRICES['week']} RUB", callback_data="buy_week")],
        [InlineKeyboardButton(text=f"Месяц - {PRICES['month']} RUB", callback_data="buy_month")],
        [InlineKeyboardButton(text=f"1 задание - {PRICES['single']} RUB", callback_data="buy_single")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    return keyboard

def info_menu_keyboard():
    """Возвращает клавиатуру для раздела 'Информация'."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Публичная оферта", callback_data="show_offer")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="show_subscribe_options")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    return keyboard

def back_to_main_menu_keyboard():
    """Возвращает клавиатуру с одной кнопкой 'Назад' в главное меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])
    return keyboard