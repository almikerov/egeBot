# database.py

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from config import SUPER_ADMIN_ID, GOOGLE_SHEETS_CREDENTIALS_JSON, SPREADSHEET_ID

# --- НАСТРОЙКА GOOGLE SHEETS ---

# Указываем области доступа (scopes)
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Аутентификация
try:
    creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_JSON, scopes=SCOPES)
    client = gspread.authorize(creds)
    # Открываем нашу таблицу
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
except FileNotFoundError:
    print(f"ОШИБКА: Файл с ключами '{GOOGLE_SHEETS_CREDENTIALS_JSON}' не найден. Убедитесь, что он существует и переменная окружения установлена правильно.")
    exit()
except Exception as e:
    print(f"ОШИБКА при подключении к Google Sheets: {e}")
    exit()


async def db_start():
    """Проверяет наличие листов и заголовков в них, создает при необходимости."""
    sheet_titles = [sh.title for sh in spreadsheet.worksheets()]
    
    # Лист 'users'
    if 'users' not in sheet_titles:
        users_sheet = spreadsheet.add_worksheet(title="users", rows="100", cols="5")
        users_sheet.append_row(['user_id', 'username', 'subscription_end_date', 'trial_tasks_used', 'single_tasks_purchased'])
    else:
        users_sheet = spreadsheet.worksheet('users')
        if not users_sheet.get_all_values():
            users_sheet.append_row(['user_id', 'username', 'subscription_end_date', 'trial_tasks_used', 'single_tasks_purchased'])

    # Лист 'admins'
    if 'admins' not in sheet_titles:
        admins_sheet = spreadsheet.add_worksheet(title="admins", rows="20", cols="1")
        admins_sheet.append_row(['user_id'])
        admins_sheet.append_row([SUPER_ADMIN_ID])
    else:
        admins_sheet = spreadsheet.worksheet('admins')
        if not admins_sheet.get_all_values():
            admins_sheet.append_row(['user_id'])
            admins_sheet.append_row([SUPER_ADMIN_ID])

    # Лист 'pending_payments'
    if 'pending_payments' not in sheet_titles:
        payments_sheet = spreadsheet.add_worksheet(title="pending_payments", rows="100", cols="5")
        payments_sheet.append_row(['invoice_id', 'user_id', 'tariff', 'amount', 'created_at'])
    else:
        payments_sheet = spreadsheet.worksheet('pending_payments')
        if not payments_sheet.get_all_values():
            payments_sheet.append_row(['invoice_id', 'user_id', 'tariff', 'amount', 'created_at'])

    print("База данных на Google Sheets готова к работе.")


async def cleanup_old_pending_payments():
    """Удаляет старые счета."""
    payments_sheet = spreadsheet.worksheet('pending_payments')
    all_payments = payments_sheet.get_all_records()
    cleanup_time_threshold = datetime.now() - timedelta(hours=24)
    rows_to_delete = []

    for idx, payment in enumerate(all_payments, start=2):
        if payment.get('created_at'):
            try:
                created_at = datetime.strptime(payment['created_at'], "%Y-%m-%d %H:%M:%S")
                if created_at < cleanup_time_threshold:
                    rows_to_delete.append(idx)
            except ValueError:
                continue

    for row_index in sorted(rows_to_delete, reverse=True):
        payments_sheet.delete_rows(row_index)
    if rows_to_delete:
        print(f"Автоматическая очистка: удалено {len(rows_to_delete)} старых счетов.")

# --- Функции для работы с платежами ---
async def add_pending_payment(invoice_id: int, user_id: int, tariff: str, amount: int):
    payments_sheet = spreadsheet.worksheet('pending_payments')
    creation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payments_sheet.append_row([invoice_id, user_id, tariff, amount, creation_time])

async def get_pending_payment(invoice_id: int) -> Optional[tuple]:
    payments_sheet = spreadsheet.worksheet('pending_payments')
    try:
        payment_cell = payments_sheet.find(str(invoice_id))
        if payment_cell:
            row_data = payments_sheet.row_values(payment_cell.row)
            return int(row_data[1]), row_data[2], int(row_data[3])
    except gspread.exceptions.CellNotFound:
        return None
    return None

async def remove_pending_payment(invoice_id: int):
    payments_sheet = spreadsheet.worksheet('pending_payments')
    try:
        payment_cell = payments_sheet.find(str(invoice_id))
        if payment_cell:
            payments_sheet.delete_rows(payment_cell.row)
    except gspread.exceptions.CellNotFound:
        pass

# --- Функции для работы с пользователями ---
async def add_user(user_id, username):
    users_sheet = spreadsheet.worksheet('users')
    try:
        user_cell = users_sheet.find(str(user_id))
        users_sheet.update_cell(user_cell.row, 2, username)
    except gspread.exceptions.CellNotFound:
        users_sheet.append_row([user_id, username, '', 0, 0])

async def get_user_by_username(username: str) -> Optional[tuple]:
    users_sheet = spreadsheet.worksheet('users')
    try:
        user_cell = users_sheet.find(username, in_column=2)
        user_id = users_sheet.cell(user_cell.row, 1).value
        return int(user_id), username
    except gspread.exceptions.CellNotFound:
        return None

async def set_subscription(user_id: int, days: int):
    users_sheet = spreadsheet.worksheet('users')
    end_date = datetime.now() + timedelta(days=days)
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    try:
        user_cell = users_sheet.find(str(user_id))
        users_sheet.update_cell(user_cell.row, 3, end_date_str)
    except gspread.exceptions.CellNotFound:
        pass

async def check_subscription(user_id: int) -> Tuple[bool, Optional[str]]:
    if await is_admin_db(user_id):
        return True, "admin"
    
    users_sheet = spreadsheet.worksheet('users')
    try:
        user_cell = users_sheet.find(str(user_id))
        end_date_str = users_sheet.cell(user_cell.row, 3).value
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < end_date:
                return True, end_date_str
    except (gspread.exceptions.CellNotFound, ValueError):
        return False, None
    return False, None

async def get_available_tasks(user_id: int) -> dict:
    users_sheet = spreadsheet.worksheet('users')
    is_subscribed, _ = await check_subscription(user_id)
    
    try:
        user_cell = users_sheet.find(str(user_id))
        row_data = users_sheet.row_values(user_cell.row)
        trials_used = int(row_data[3])
        single_purchased = int(row_data[4])
        trials_left = max(0, 2 - trials_used)
        single_left = single_purchased
    except (gspread.exceptions.CellNotFound, IndexError, ValueError):
        # Если пользователь не найден или данные некорректны, возвращаем значения по умолчанию
        await add_user(user_id, 'unknown') # Добавляем пользователя, если его нет
        return {"is_subscribed": is_subscribed, "trials_left": 2, "single_left": 0}

    return {"is_subscribed": is_subscribed, "trials_left": trials_left, "single_left": single_left}

async def use_task(user_id: int):
    is_subscribed, _ = await check_subscription(user_id)
    if is_subscribed:
        return

    users_sheet = spreadsheet.worksheet('users')
    try:
        user_cell = users_sheet.find(str(user_id))
        row_data = users_sheet.row_values(user_cell.row)
        trials_used = int(row_data[3])
        single_purchased = int(row_data[4])
        
        if trials_used < 2:
            users_sheet.update_cell(user_cell.row, 4, trials_used + 1)
        elif single_purchased > 0:
            users_sheet.update_cell(user_cell.row, 5, single_purchased - 1)
    except (gspread.exceptions.CellNotFound, IndexError, ValueError):
        pass

async def add_single_tasks(user_id: int, count: int):
    users_sheet = spreadsheet.worksheet('users')
    try:
        user_cell = users_sheet.find(str(user_id))
        current_single = int(users_sheet.cell(user_cell.row, 5).value)
        users_sheet.update_cell(user_cell.row, 5, current_single + count)
    except (gspread.exceptions.CellNotFound, ValueError):
        pass

async def get_subscribed_users() -> List[tuple]:
    users_sheet = spreadsheet.worksheet('users')
    all_users = users_sheet.get_all_records()
    subscribed = []
    now = datetime.now()
    for user in all_users:
        if user.get('subscription_end_date'):
            try:
                end_date = datetime.strptime(user['subscription_end_date'], "%Y-%m-%d %H:%M:%S")
                if end_date > now:
                    subscribed.append((user['user_id'], user['username'], user['subscription_end_date']))
            except ValueError:
                continue
    return subscribed

# --- Функции для работы с админами ---
async def is_admin_db(user_id: int) -> bool:
    admins_sheet = spreadsheet.worksheet('admins')
    admin_ids = admins_sheet.col_values(1)
    return str(user_id) in admin_ids

async def get_admins() -> List[int]:
    admins_sheet = spreadsheet.worksheet('admins')
    admin_ids_str = admins_sheet.col_values(1)
    return [int(id_str) for id_str in admin_ids_str if id_str.isdigit()]

async def add_admin(user_id: int):
    if not await is_admin_db(user_id):
        admins_sheet = spreadsheet.worksheet('admins')
        admins_sheet.append_row([user_id])

async def remove_admin(user_id: int):
    if user_id == SUPER_ADMIN_ID:
        print("Попытка удалить супер-админа заблокирована.")
        return
    
    admins_sheet = spreadsheet.worksheet('admins')
    try:
        admin_cell = admins_sheet.find(str(user_id))
        admins_sheet.delete_rows(admin_cell.row)
    except gspread.exceptions.CellNotFound:
        pass