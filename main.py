# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
# --- ДОБАВЬТЕ ЭТОТ ИМПОРТ ---
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_TOKEN
from handlers import router
from database import db_start

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # --- ИЗМЕНИТЕ ЭТУ СТРОКУ ---
    # Создаем Dispatcher, передавая ему хранилище для состояний
    dp = Dispatcher(storage=MemoryStorage())
    
    bot = Bot(token=TELEGRAM_TOKEN)
    
    dp.include_router(router)
    await db_start()
    
    print("Бот готов к запуску!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")