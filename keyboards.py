# keyboards.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from typing import List

def main_menu_keyboard():
    """Возвращает клавиатуру главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Получить задание", callback_data="get_task")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="show_subscribe_options")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="show_info")]
    ])

def task_type_keyboard(task_types: List[str]):
    """Создает клавиатуру для выбора типа задания и добавляет кнопку получения по ID."""
    buttons = []
    for title in task_types:
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"select_task_{title}")])
    
    buttons.append([InlineKeyboardButton(text="🔎 Найти по ID", callback_data="get_task_by_id_prompt")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def web_app_keyboard(url: str):
    """Создает клавиатуру с одной кнопкой для запуска веб-приложения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Открыть веб-приложение", 
            web_app=WebAppInfo(url=url)
        )]
    ])

def subscribe_menu_keyboard(prices: dict):
    """Возвращает клавиатуру для выбора тарифа подписки с актуальными ценами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Неделя - {prices.get('week', 'N/A')} RUB", callback_data="buy_week")],
        [InlineKeyboardButton(text=f"Месяц - {prices.get('month', 'N/A')} RUB", callback_data="buy_month")],
        [InlineKeyboardButton(text=f"1 задание - {prices.get('single', 'N/A')} RUB", callback_data="buy_single")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    
def payment_keyboard(payment_link: str, amount: int):
    """Клавиатура для оплаты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {amount} RUB", url=payment_link)],
        [InlineKeyboardButton(text="✅ Я оплатил, проверить", callback_data="check_robokassa_payment")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_subscribe_options")]
    ])

def payment_failed_keyboard():
    """Клавиатура при неудачной проверке платежа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать еще раз", callback_data="check_robokassa_payment")],
        [InlineKeyboardButton(text="⬅️ Выбрать другой тариф", callback_data="show_subscribe_options")]
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
        [InlineKeyboardButton(text="💰 Изменить цены", callback_data="admin_edit_prices")],
        [InlineKeyboardButton(text="👑 Администраторы", callback_data="admin_manage_admins")],
        [InlineKeyboardButton(text="👥 Пользователи с подпиской", callback_data="admin_view_subscribed")],
        # НОВАЯ КНОПКА
        [InlineKeyboardButton(text="👨‍💻 Управление пользователями", callback_data="admin_manage_users")],
        [InlineKeyboardButton(text="⬅️ Выйти из админ-панели", callback_data="main_menu")]
    ])

# НОВОЕ МЕНЮ
def user_management_keyboard():
    """Клавиатура для управления пользователями."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓️ Выдать подписку", callback_data="admin_give_subscription")],
        [InlineKeyboardButton(text="🎟️ Начислить задания", callback_data="admin_add_tasks")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
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

def admin_management_keyboard():
    """Клавиатура для управления администраторами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Показать всех", callback_data="admin_view_admins")],
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])

def back_to_admins_menu_keyboard():
    """Клавиатура для возврата в меню управления администраторами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_manage_admins")]
    ])