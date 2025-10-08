# database.py

import sqlite3 as sq
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from config import SUPER_ADMIN_ID

async def cleanup_old_pending_payments():
    """Удаляет из pending_payments счета, созданные более 24 часов назад."""
    db = sq.connect('users.db')
    cur = db.cursor()
    
    # Добавляем в таблицу столбец для времени создания, если его нет
    try:
        cur.execute("ALTER TABLE pending_payments ADD COLUMN created_at TEXT")
    except sq.OperationalError:
        # Столбец уже существует, ничего не делаем
        pass

    # Устанавливаем текущее время для записей, где оно отсутствует
    cur.execute("UPDATE pending_payments SET created_at = ? WHERE created_at IS NULL", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    
    # Вычисляем время 24 часа назад
    cleanup_time_threshold = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Удаляем старые записи
    cur.execute("DELETE FROM pending_payments WHERE created_at < ?", (cleanup_time_threshold,))
    
    deleted_rows = cur.rowcount
    if deleted_rows > 0:
        print(f"Автоматическая очистка: удалено {deleted_rows} старых записей из pending_payments.")
        
    db.commit()
    db.close()

async def db_start():
    """
    Инициализирует базу данных и создает таблицы, если они не существуют.
    """
    db = sq.connect('users.db')
    cur = db.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            subscription_end_date TEXT,
            trial_tasks_used INTEGER DEFAULT 0,
            single_tasks_purchased INTEGER DEFAULT 0
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    # ИЗМЕНЕНО: invoice_id теперь TEXT для предотвращения переполнения
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            tariff TEXT,
            amount INTEGER,
            created_at TEXT 
        )
    """)
    
    cur.execute("SELECT 1 FROM admins")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))
        print(f"Super admin with ID {SUPER_ADMIN_ID} added to the database.")

    db.commit()
    db.close()

async def add_pending_payment(invoice_id: str, user_id: int, tariff: str, amount: int):
    """Добавляет информацию о новом счете в базу данных."""
    db = sq.connect('users.db')
    cur = db.cursor()
    # Записываем время создания счета
    creation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO pending_payments (invoice_id, user_id, tariff, amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (invoice_id, user_id, tariff, amount, creation_time)
    )
    db.commit()
    db.close()

async def get_pending_payment(invoice_id: str) -> Optional[tuple]:
    """Получает информацию о счете из базы данных."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT user_id, tariff, amount FROM pending_payments WHERE invoice_id = ?", (invoice_id,))
    payment_data = cur.fetchone()
    db.close()
    return payment_data

async def remove_pending_payment(invoice_id: str):
    """Удаляет информацию о счете после успешной оплаты."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("DELETE FROM pending_payments WHERE invoice_id = ?", (invoice_id,))
    db.commit()
    db.close()

async def add_user(user_id, username):
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    else:
        # Обновляем username, если пользователь его сменил
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    db.commit()
    db.close()

async def get_user_by_username(username: str) -> Optional[tuple]:
    """Находит пользователя в таблице users по его username."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    db.close()
    return user

async def set_subscription(user_id: int, days: int):
    end_date = datetime.now() + timedelta(days=days)
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("UPDATE users SET subscription_end_date = ? WHERE user_id = ?", (end_date_str, user_id))
    db.commit()
    db.close()

async def check_subscription(user_id: int) -> Tuple[bool, Optional[str]]:
    if await is_admin_db(user_id):
        return True, "admin"

    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()

    if result and result[0]:
        end_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < end_date:
            return True, result[0]
            
    return False, None

async def get_available_tasks(user_id: int) -> dict:
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()
    
    if not result:
        return {"is_subscribed": False, "trials_left": 2, "single_left": 0}
        
    is_subscribed, _ = await check_subscription(user_id)
    trials_used, single_purchased = result
    
    return {
        "is_subscribed": is_subscribed,
        "trials_left": max(0, 2 - trials_used),
        "single_left": single_purchased
    }

async def use_task(user_id: int):
    is_subscribed, _ = await check_subscription(user_id)
    if is_subscribed:
        return

    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    if not result:
        db.close()
        return

    trials_used, single_purchased = result
    if trials_used < 2:
        cur.execute("UPDATE users SET trial_tasks_used = trial_tasks_used + 1 WHERE user_id = ?", (user_id,))
    elif single_purchased > 0:
        cur.execute("UPDATE users SET single_tasks_purchased = single_tasks_purchased - 1 WHERE user_id = ?", (user_id,))
    
    db.commit()
    db.close()

async def add_single_tasks(user_id: int, count: int):
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("UPDATE users SET single_tasks_purchased = single_tasks_purchased + ? WHERE user_id = ?", (count, user_id))
    db.commit()
    db.close()

async def get_subscribed_users() -> List[tuple]:
    db = sq.connect('users.db')
    cur = db.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT user_id, username, subscription_end_date FROM users WHERE subscription_end_date > ?", (now_str,))
    users = cur.fetchall()
    db.close()
    return users

async def is_admin_db(user_id: int) -> bool:
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()
    return result is not None

async def get_admins() -> List[int]:
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in cur.fetchall()]
    db.close()
    return admins

async def add_admin(user_id: int):
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    db.commit()
    db.close()

async def remove_admin(user_id: int):
    if user_id == SUPER_ADMIN_ID:
        print("Attempt to remove super admin was blocked.")
        return
        
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    db.commit()
    db.close()