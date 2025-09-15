# price_manager.py

import json
import os

PRICES_FILE = 'prices.json'
DEFAULT_PRICES = {
    "week": 299,
    "month": 799,
    "single": 50
}

def load_prices():
    """Загружает цены из JSON-файла. Если файл не найден, создает его с ценами по умолчанию."""
    if not os.path.exists(PRICES_FILE):
        save_prices(DEFAULT_PRICES)
        return DEFAULT_PRICES
    
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # В случае ошибки или пустого файла, перезаписываем с дефолтными ценами
        save_prices(DEFAULT_PRICES)
        return DEFAULT_PRICES

def save_prices(prices_data):
    """Сохраняет словарь с ценами в JSON-файл."""
    with open(PRICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(prices_data, f, indent=4, ensure_ascii=False)