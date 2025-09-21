# main.py

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import TELEGRAM_TOKEN
from handlers import router
from database import db_start, cleanup_old_pending_payments

# URL вебхука будет браться из переменных окружения Render
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}" # Используем токен в пути для секретности

# Настройки веб-сервера
WEB_SERVER_HOST = "0.0.0.0"
# Render предоставляет порт в переменной окружения PORT
WEB_SERVER_PORT = int(os.getenv('PORT', 8000))

async def on_startup(bot: Bot):
    """Действия при запуске бота: инициализация БД и установка вебхука."""
    await db_start()
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    print("Вебхук успешно установлен!")

async def on_shutdown(bot: Bot):
    """Действия при остановке бота: удаление вебхука."""
    await bot.delete_webhook()
    print("Вебхук удален.")

async def scheduled_cleanup(wait_for_seconds: int):
    """Запускает функцию очистки каждые N секунд."""
    while True:
        await asyncio.sleep(wait_for_seconds)
        await cleanup_old_pending_payments()

async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Регистрируем функции запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запускаем фоновую задачу для очистки
    asyncio.create_task(scheduled_cleanup(86400))

    # Создаем веб-приложение aiohttp
    app = web.Application()
    
    # Создаем обработчик вебхуков для aiogram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    # Регистрируем его в приложении
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настраиваем и запускаем приложение
    setup_application(app, dp, bot=bot)
    
    print(f"Бот готов к запуску на порту {WEB_SERVER_PORT}!")
    
    # Запускаем веб-сервер
    await web._run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")