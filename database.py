# database.py

import sqlite3 as sq
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from config import SUPER_ADMIN_ID

async def db_start():
    """
    Инициализирует базу данных и создает таблицы, если они не существуют.
    """
    db = sq.connect('users.db')
    cur = db.cursor()
    
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            subscription_end_date TEXT,
            trial_tasks_used INTEGER DEFAULT 0,
            single_tasks_purchased INTEGER DEFAULT 0
        )
    """)
    
    # Таблица администраторов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    # Проверяем, есть ли вообще администраторы
    cur.execute("SELECT 1 FROM admins")
    if cur.fetchone() is None:
        # Если нет, добавляем супер-админа из конфига
        cur.execute("INSERT INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))
        print(f"Super admin with ID {SUPER_ADMIN_ID} added to the database.")

    db.commit()
    db.close()

async def add_user(user_id, username):
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        db.commit()
    db.close()

async def set_subscription(user_id: int, days: int):
    end_date = datetime.now() + timedelta(days=days)
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("UPDATE users SET subscription_end_date = ? WHERE user_id = ?", (end_date_str, user_id))
    db.commit()
    db.close()

async def check_subscription(user_id: int) -> Tuple[bool, Optional[str]]:
    """
    Проверяет подписку и возвращает кортеж (статус_подписки, дата_окончания).
    Админы всегда имеют активную подписку.
    """
    if await is_admin_db(user_id):
        # Для админов возвращаем "вечную" подписку
        return True, (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")

    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()

    if result and result[0]:
        end_date_str = result[0]
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < end_date:
            return True, end_date_str
            
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
    """Возвращает список пользователей (id, username, end_date) с активной подпиской."""
    db = sq.connect('users.db')
    cur = db.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT user_id, username, subscription_end_date FROM users WHERE subscription_end_date > ?", (now_str,))
    users = cur.fetchall()
    db.close()
    return users

# --- Функции для управления администраторами ---

async def is_admin_db(user_id: int) -> bool:
    """Проверяет, есть ли user_id в таблице администраторов."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()
    return result is not None

async def get_admins() -> List[int]:
    """Возвращает список ID всех администраторов."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT user_id FROM admins")
    # Преобразуем список кортежей [(id,), (id,)] в простой список [id, id]
    admins = [row[0] for row in cur.fetchall()]
    db.close()
    return admins

async def add_admin(user_id: int):
    """Добавляет нового администратора."""
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    db.commit()
    db.close()

async def remove_admin(user_id: int):
    """Удаляет администратора, если он не является супер-админом."""
    if user_id == SUPER_ADMIN_ID:
        print("Attempt to remove super admin was blocked.")
        return
        
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    db.commit()
    db.close()