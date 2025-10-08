# robokassa_api.py

import hashlib
import aiohttp
from config import (
    ROBOKASSA_MERCHANT_LOGIN,
    ROBOKASSA_PASSWORD_1,
    ROBOKASSA_PASSWORD_2,
    ROBOKASSA_TEST_PASSWORD_1,
    ROBOKASSA_TEST_PASSWORD_2
)

# --- ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА ---
# 1 = Тестовый режим, 0 = Боевой режим
IS_TEST = 1

def _get_credentials():
    """Возвращает правильные пароли в зависимости от режима."""
    if IS_TEST == 1:
        print("[ROBOKASSA LOG] Используются ТЕСТОВЫЕ пароли.")
        return ROBOKASSA_TEST_PASSWORD_1, ROBOKASSA_TEST_PASSWORD_2
    else:
        print("[ROBOKASSA LOG] Используются БОЕВЫЕ пароли.")
        return ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2

def generate_payment_link(amount: int, invoice_id: int) -> str:
    """
    Генерирует ссылку на оплату. Эта часть работала и остается без изменений.
    """
    password_1, _ = _get_credentials()
    description = "Подписка на AI-репетитора"
    
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{password_1}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    print("\n--- [ROBOKASSA LOG] ГЕНЕРАЦИЯ ССЫЛКИ НА ОПЛАТУ ---")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print("---------------------------------------------------\n")

    link = (
        f"https://auth.robokassa.ru/Merchant/Index.aspx?"
        f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
        f"OutSum={amount}&"
        f"InvId={invoice_id}&"
        f"Description={description}&"
        f"SignatureValue={signature_hash}&"
        f"IsTest={IS_TEST}"
    )
    return link

async def check_payment(invoice_id: int) -> bool:
    """
    Проверяет статус оплаты счета через НОВЫЙ JSON API.
    """
    _, password_2 = _get_credentials()
    
    # Подпись для JSON API
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password_2}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    # URL для нового JSON API
    url = "https://auth.robokassa.ru/Merchant/Api/OpStateExt"
    
    # Параметры запроса передаются в виде JSON
    payload = {
        "MerchantLogin": ROBOKASSA_MERCHANT_LOGIN,
        "InvoiceID": invoice_id,
        "Signature": signature_hash,
        "IsTest": IS_TEST
    }

    print("\n--- [ROBOKASSA LOG] ПРОВЕРКА СТАТУСА (НОВЫЙ JSON API) ---")
    print(f"URL ДЛЯ ЗАПРОСА: {url}")
    print(f"ОТПРАВЛЯЕМЫЙ JSON: {payload}")
    print("----------------------------------------------------\n")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                response_json = await response.json()
                print(f"[ROBOKASSA LOG] ПОЛУЧЕН ОТВЕТ (JSON):\n{response_json}\n")

                if response.status != 200:
                    print(f"[ROBOKASSA LOG] ОШИБКА: HTTP статус {response.status}")
                    return False

                result_code = response_json.get("Result", {}).get("Code", -1)
                if result_code != 0:
                    error_desc = response_json.get("Result", {}).get("Description", "Нет описания")
                    print(f"[ROBOKASSA LOG] ОШИБКА В ОТВЕТЕ: Код {result_code} - {error_desc}")
                    return False

                # В JSON API статус операции находится в State.Code
                state_code = response_json.get("State", {}).get("Code", -1)
                if state_code == 100:
                    print("[ROBOKASSA LOG] УСПЕХ: Платеж подтвержден (код 100).")
                    return True
                else:
                    print(f"[ROBOKASSA LOG] ИНФО: Платеж не подтвержден. Код статуса: {state_code}")
                    return False
        except Exception as e:
            print(f"[ROBOKASSA LOG] КРИТИЧЕСКАЯ ОШИБКА: {e}")
            return False