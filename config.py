# config.py

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# --- Ключи и токены ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Для чтения заданий из Google Sheets

# Загружаем ключи Gemini и разделяем их по запятой
gemini_api_keys_str = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [key.strip() for key in gemini_api_keys_str.split(',') if key.strip()]

# --- Данные для Robokassa ---
ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN")
ROBOKASSA_PASSWORD_1 = os.getenv("ROBOKASSA_PASSWORD_1")
ROBOKASSA_PASSWORD_2 = os.getenv("ROBOKASSA_PASSWORD_2")

# --- ДАННЫЕ ДЛЯ БАЗЫ ДАННЫХ ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Проверка переменных ---
# --- ИЗМЕНЕНИЕ ЗДЕСЬ: Добавлена проверка DATABASE_URL ---
if not all([TELEGRAM_TOKEN, ADMIN_PASSWORD, GOOGLE_API_KEY, ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2, DATABASE_URL]):
    raise ValueError("ОШИБКА: Одна или несколько основных переменных окружения не загружены.")

if not GEMINI_API_KEYS:
    raise ValueError("ОШИБКА: Не найден ни один GEMINI_API_KEY. Проверьте ваш .env файл.")

# --- Параметры бота ---
SUPER_ADMIN_ID = 1233372901 # ЗАМЕНИТЕ НА ВАШ ID