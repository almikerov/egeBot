# config.py

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# --- Ключи и токены ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Ключ для Google Sheets (чтение заданий)

# Загружаем ключи Gemini и разделяем их по запятой
gemini_api_keys_str = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [key.strip() for key in gemini_api_keys_str.split(',') if key.strip()]

# --- Данные для Robokassa ---
ROBOKASSA_MERCHANT_LOGIN = os.getenv("ROBOKASSA_MERCHANT_LOGIN")
ROBOKASSA_PASSWORD_1 = os.getenv("ROBOKASSA_PASSWORD_1")
ROBOKASSA_PASSWORD_2 = os.getenv("ROBOKASSA_PASSWORD_2")

# --- ДАННЫЕ ДЛЯ GOOGLE SHEETS В КАЧЕСТВЕ БД ---
# Имя вашего JSON файла с ключами сервисного аккаунта
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
# ID вашей таблицы (из URL: docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Проверка переменных ---
if not all([TELEGRAM_TOKEN, ADMIN_PASSWORD, GOOGLE_API_KEY, ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2, GOOGLE_SHEETS_CREDENTIALS_JSON, SPREADSHEET_ID]):
    raise ValueError("ОШИБКА: Одна или несколько основных переменных окружения не загружены. Проверьте ваш .env файл.")

if not GEMINI_API_KEYS:
    raise ValueError("ОШИБКА: Не найден ни один GEMINI_API_KEY. Проверьте ваш .env файл.")

# --- Параметры бота ---
# Укажите Telegram ID главного администратора. Его нельзя будет удалить через бота.
# Узнать можно у бота @userinfobot
SUPER_ADMIN_ID = 1233372901 # ЗАМЕНИТЕ НА ВАШ ID