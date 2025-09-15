# database.py

import sqlite3 as sq
from datetime import datetime, timedelta
from config import ADMIN_IDS

async def db_start():
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

async def check_subscription(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT subscription_end_date FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()
    if result and result[0]:
        end_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < end_date:
            return True
    return False

async def get_available_tasks(user_id: int) -> dict:
    db = sq.connect('users.db')
    cur = db.cursor()
    cur.execute("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    db.close()
    if not result:
        return {"is_subscribed": False, "trials_left": 2, "single_left": 0}
    is_subscribed = await check_subscription(user_id)
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