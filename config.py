# config.py

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# --- ФУНКЦИЯ ДЛЯ БЕЗОПАСНОГО ЧТЕНИЯ ПЕРЕМЕННЫХ ---
def get_env_variable(var_name: str) -> str:
    """Получает переменную из .env и очищает ее от лишних символов."""
    value = os.getenv(var_name)
    if value:
        # .strip() удаляет все пробелы и невидимые символы (включая BOM) с начала и конца строки
        return value.strip()
    return None

# --- Ключи и токены ---
TELEGRAM_TOKEN = get_env_variable("TELEGRAM_TOKEN")
ADMIN_PASSWORD = get_env_variable("ADMIN_PASSWORD")
GOOGLE_API_KEY = get_env_variable("GOOGLE_API_KEY")

# Загружаем ключи Gemini и разделяем их по запятой
gemini_api_keys_str = get_env_variable("GEMINI_API_KEY") or ""
GEMINI_API_KEYS = [key.strip() for key in gemini_api_keys_str.split(',') if key.strip()]

# --- Данные для Robokassa (теперь читаются безопасно) ---
ROBOKASSA_MERCHANT_LOGIN = get_env_variable("ROBOKASSA_MERCHANT_LOGIN")
# Боевые пароли
ROBOKASSA_PASSWORD_1 = get_env_variable("ROBOKASSA_PASSWORD_1")
ROBOKASSA_PASSWORD_2 = get_env_variable("ROBOKASSA_PASSWORD_2")
# Тестовые пароли
ROBOKASSA_TEST_PASSWORD_1 = get_env_variable("ROBOKASSA_TEST_PASSWORD_1")
ROBOKASSA_TEST_PASSWORD_2 = get_env_variable("ROBOKASSA_TEST_PASSWORD_2")


# --- Проверка переменных ---
if not all([TELEGRAM_TOKEN, ADMIN_PASSWORD, ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2, ROBOKASSA_TEST_PASSWORD_1, ROBOKASSA_TEST_PASSWORD_2]):
    raise ValueError("ОШИБКА: Одна или несколько переменных окружения (включая тестовые для Robokassa) не загружены. Проверьте ваш .env файл.")

if not GEMINI_API_KEYS:
    raise ValueError("ОШИБКА: Не найден ни один GEMINI_API_KEY. Проверьте ваш .env файл.")

# --- Параметры бота ---
SUPER_ADMIN_ID = 1233372901 # ЗАМЕНИТЕ НА ВАШ ID