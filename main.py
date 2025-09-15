# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_TOKEN
from handlers import router
# ИЗМЕНЕНО: Импортируем db_start и функцию очистки отдельно
from database import db_start, cleanup_old_pending_payments

# НОВАЯ ФУНКЦИЯ: Планировщик для периодической очистки
async def scheduled_cleanup(wait_for_seconds: int):
    """Запускает функцию очистки каждые N секунд."""
    while True:
        await asyncio.sleep(wait_for_seconds)
        await cleanup_old_pending_payments()
        print(f"Выполнена плановая очистка старых счетов.")


async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Создаем Dispatcher, передавая ему хранилище для состояний
    dp = Dispatcher(storage=MemoryStorage())
    
    bot = Bot(token=TELEGRAM_TOKEN)
    
    dp.include_router(router)
    # Сначала инициализируем БД
    await db_start()
    
    # ИЗМЕНЕНО: Запускаем фоновую задачу для очистки каждые 24 часа (86400 секунд)
    asyncio.create_task(scheduled_cleanup(86400))
    
    print("Бот готов к запуску!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")