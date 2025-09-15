# database.py

import sqlite3 as sq
from datetime import datetime, timedelta
from typing import Tuple, Optional
from config import ADMIN_IDS

# ... (остальной код файла без изменений до функции check_subscription) ...

async def set_subscription(user_id: int, days: int):
    end_date = datetime.now() + timedelta(days=days)
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("UPDATE users SET subscription_end_date = ? WHERE user_id = ?", (end_date_str, user_id))
    db.commit()
    db.close()

# --- ИЗМЕНЕННАЯ ФУНКЦИЯ ---
async def check_subscription(user_id: int) -> Tuple[bool, Optional[str]]:
    """
    Проверяет подписку и возвращает кортеж (статус_подписки, дата_окончания).
    """
    if user_id in ADMIN_IDS:
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

# ... (остальной код файла без изменений) ...

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
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = ?", (user_id,))
    trials_used, single_purchased = cur.fetchone()
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