# config.py

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Загружаем токены и ключи из окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Данные для Robokassa
ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN")
ROBOKASSA_PASSWORD_1 = os.getenv("ROBOKASSA_PASSWORD_1")
ROBOKASSA_PASSWORD_2 = os.getenv("ROBOKASSA_PASSWORD_2")

# Проверка, что все переменные загружены
if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, ADMIN_PASSWORD, ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2]):
    raise ValueError("ОШИБКА: Одна или несколько переменных окружения не были загружены. Проверьте ваш .env файл.")

# --- Параметры бота ---

# Укажите ваш Telegram ID. Узнать можно у бота @userinfobot
ADMIN_IDS = [1233372901] 

# Цены на тарифы (в рублях)
PRICES = {
    "week": 299,
    "month": 799,
    "single": 50
}