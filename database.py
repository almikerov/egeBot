# database.py

import asyncpg
import asyncio
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from config import SUPER_ADMIN_ID, DATABASE_URL

# --- Пул соединений для высокой производительности ---
pool = None

async def get_pool():
    """Инициализирует и возвращает пул соединений к базе данных."""
    global pool
    if pool is None:
        try:
            pool = await asyncpg.create_pool(DATABASE_URL)
        except Exception as e:
            print(f"ОШИБКА: Не удалось подключиться к базе данных: {e}")
            exit()
    return pool

# --- ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ---
async def db_start():
    """Создает таблицы в базе данных, если они не существуют."""
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                subscription_end_date TIMESTAMP,
                trial_tasks_used INTEGER DEFAULT 0,
                single_tasks_purchased INTEGER DEFAULT 0
            );""")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY
            );""")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                invoice_id BIGINT PRIMARY KEY,
                user_id BIGINT,
                tariff TEXT,
                amount INTEGER,
                created_at TIMESTAMP
            );""")
        
        # Добавляем супер-админа, если его нет
        super_admin_exists = await conn.fetchval("SELECT 1 FROM admins WHERE user_id = $1", SUPER_ADMIN_ID)
        if not super_admin_exists:
            await conn.execute("INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", SUPER_ADMIN_ID)
            print(f"Super admin with ID {SUPER_ADMIN_ID} added to the database.")

    finally:
        await (await get_pool()).release(conn)
    print("База данных PostgreSQL готова к работе.")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ ---

async def cleanup_old_pending_payments():
    conn = await (await get_pool()).acquire()
    try:
        cleanup_time_threshold = datetime.now() - timedelta(hours=24)
        await conn.execute("DELETE FROM pending_payments WHERE created_at < $1", cleanup_time_threshold)
    finally: await (await get_pool()).release(conn)

async def add_pending_payment(invoice_id: int, user_id: int, tariff: str, amount: int):
    conn = await (await get_pool()).acquire()
    try:
        creation_time = datetime.now()
        await conn.execute("INSERT INTO pending_payments (invoice_id, user_id, tariff, amount, created_at) VALUES ($1, $2, $3, $4, $5)",
                           invoice_id, user_id, tariff, amount, creation_time)
    finally: await (await get_pool()).release(conn)

async def get_pending_payment(invoice_id: int) -> Optional[tuple]:
    conn = await (await get_pool()).acquire()
    try:
        row = await conn.fetchrow("SELECT user_id, tariff, amount FROM pending_payments WHERE invoice_id = $1", invoice_id)
        return tuple(row) if row else None
    finally: await (await get_pool()).release(conn)

async def remove_pending_payment(invoice_id: int):
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("DELETE FROM pending_payments WHERE invoice_id = $1", invoice_id)
    finally: await (await get_pool()).release(conn)

async def add_user(user_id, username):
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("""
            INSERT INTO users (user_id, username, trial_tasks_used, single_tasks_purchased) VALUES ($1, $2, 0, 0)
            ON CONFLICT (user_id) DO UPDATE SET username = $2
        """, user_id, username)
    finally: await (await get_pool()).release(conn)

async def get_user_by_username(username: str) -> Optional[tuple]:
    conn = await (await get_pool()).acquire()
    try:
        row = await conn.fetchrow("SELECT user_id, username FROM users WHERE username = $1", username)
        return tuple(row) if row else None
    finally: await (await get_pool()).release(conn)

async def set_subscription(user_id: int, days: int):
    conn = await (await get_pool()).acquire()
    try:
        end_date = datetime.now() + timedelta(days=days)
        await conn.execute("UPDATE users SET subscription_end_date = $1 WHERE user_id = $2", end_date, user_id)
    finally: await (await get_pool()).release(conn)

async def check_subscription(user_id: int) -> Tuple[bool, Optional[str]]:
    if await is_admin_db(user_id): return True, "admin"
    conn = await (await get_pool()).acquire()
    try:
        end_date = await conn.fetchval("SELECT subscription_end_date FROM users WHERE user_id = $1", user_id)
        if end_date and datetime.now() < end_date:
            return True, end_date.strftime("%Y-%m-%d %H:%M:%S")
    finally: await (await get_pool()).release(conn)
    return False, None

async def get_available_tasks(user_id: int) -> dict:
    conn = await (await get_pool()).acquire()
    try:
        is_subscribed, _ = await check_subscription(user_id)
        row = await conn.fetchrow("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = $1", user_id)
        if not row:
            # Если пользователя нет, добавляем его
            await add_user(user_id, 'unknown')
            return {"is_subscribed": is_subscribed, "trials_left": 2, "single_left": 0}
        trials_used, single_purchased = row
        return {"is_subscribed": is_subscribed, "trials_left": max(0, 2 - trials_used), "single_left": single_purchased}
    finally: await (await get_pool()).release(conn)

async def use_task(user_id: int):
    is_subscribed, _ = await check_subscription(user_id)
    if is_subscribed: return
    conn = await (await get_pool()).acquire()
    try:
        row = await conn.fetchrow("SELECT trial_tasks_used, single_tasks_purchased FROM users WHERE user_id = $1", user_id)
        if not row: return
        trials_used, single_purchased = row
        if trials_used < 2:
            await conn.execute("UPDATE users SET trial_tasks_used = trial_tasks_used + 1 WHERE user_id = $1", user_id)
        elif single_purchased > 0:
            await conn.execute("UPDATE users SET single_tasks_purchased = single_tasks_purchased - 1 WHERE user_id = $1", user_id)
    finally: await (await get_pool()).release(conn)

async def add_single_tasks(user_id: int, count: int):
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("UPDATE users SET single_tasks_purchased = single_tasks_purchased + $1 WHERE user_id = $2", count, user_id)
    finally: await (await get_pool()).release(conn)

async def get_subscribed_users() -> List[tuple]:
    conn = await (await get_pool()).acquire()
    try:
        rows = await conn.fetch("SELECT user_id, username, subscription_end_date FROM users WHERE subscription_end_date > NOW()")
        return [(r['user_id'], r['username'], r['subscription_end_date'].strftime("%Y-%m-%d %H:%M:%S")) for r in rows]
    finally: await (await get_pool()).release(conn)

async def is_admin_db(user_id: int) -> bool:
    conn = await (await get_pool()).acquire()
    try:
        return await conn.fetchval("SELECT 1 FROM admins WHERE user_id = $1", user_id) is not None
    finally: await (await get_pool()).release(conn)

async def get_admins() -> List[int]:
    conn = await (await get_pool()).acquire()
    try:
        rows = await conn.fetch("SELECT user_id FROM admins")
        return [r['user_id'] for r in rows]
    finally: await (await get_pool()).release(conn)

async def add_admin(user_id: int):
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", user_id)
    finally: await (await get_pool()).release(conn)

async def remove_admin(user_id: int):
    if user_id == SUPER_ADMIN_ID: return
    conn = await (await get_pool()).acquire()
    try:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)
    finally: await (await get_pool()).release(conn)