# keyboards.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    """Возвращает клавиатуру главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Получить задание", callback_data="get_task")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="show_subscribe_options")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="show_info")]
    ])

def subscribe_menu_keyboard(prices: dict):
    """Возвращает клавиатуру для выбора тарифа подписки с актуальными ценами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Неделя - {prices.get('week', 'N/A')} RUB", callback_data="buy_week")],
        [InlineKeyboardButton(text=f"Месяц - {prices.get('month', 'N/A')} RUB", callback_data="buy_month")],
        [InlineKeyboardButton(text=f"1 задание - {prices.get('single', 'N/A')} RUB", callback_data="buy_single")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def info_menu_keyboard():
    """Возвращает клавиатуру для раздела 'Информация'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Публичная оферта", callback_data="show_offer")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="show_subscribe_options")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def back_to_main_menu_keyboard():
    """Возвращает клавиатуру с одной кнопкой 'Назад' в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])

# --- Клавиатуры для админ-панели ---

def admin_menu_keyboard():
    """Возвращает клавиатуру главного меню админ-панели."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Узнать текущий промпт", callback_data="admin_view_prompt")],
        [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data="admin_edit_prompt")],
        [InlineKeyboardButton(text="💰 Изменить цены", callback_data="admin_edit_prices")]
    ])

def back_to_admin_menu_keyboard():
    """Возвращает клавиатуру с кнопкой 'Назад' в меню администратора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_menu")]
    ])

def edit_prices_keyboard():
    """Возвращает клавиатуру для выбора тарифа для изменения цены."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Неделя", callback_data="edit_price_week")],
        [InlineKeyboardButton(text="Месяц", callback_data="edit_price_month")],
        [InlineKeyboardButton(text="1 задание", callback_data="edit_price_single")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])