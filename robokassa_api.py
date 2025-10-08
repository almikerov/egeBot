# robokassa_api.py

import hashlib
import aiohttp
import xml.etree.ElementTree as ET
from config import ROBOKASSA_MERCHANT_LOGIN

# --- ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА ---
# 1 = Тестовый режим, 0 = Боевой режим
# Устанавливаем тестовый режим для отладки.
IS_TEST = 1

def generate_payment_link(user_id: int, amount: int, invoice_id: int, password_1: str) -> str:
    """
    Генерирует ссылку на оплату с правильной подписью.
    """
    description = "Подписка на AI-репетитора"
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{password_1}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    print("\n--- [ROBOKASSA LOG] ГЕНЕРАЦИЯ ССЫЛКИ НА ОПЛАТУ ---")
    print(f"РЕЖИМ: {'ТЕСТОВЫЙ' if IS_TEST == 1 else 'БОЕВОЙ'}")
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
        f"shp_user={user_id}&"
        f"IsTest={IS_TEST}"
    )
    return link

async def check_payment(invoice_id: int, user_id: int, password_2: str) -> bool:
    """
    Проверяет статус оплаты счета через XML интерфейс Робокассы.
    """
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password_2}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    # ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Добавлен параметр IsTest в URL для проверки
    url = (
        f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
        f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
        f"InvoiceID={invoice_id}&"
        f"Signature={signature_hash}&"
        f"IsTest={IS_TEST}"  # <--- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ
    )

    print("\n--- [ROBOKASSA LOG] ПРОВЕРКА СТАТУСА ПЛАТЕЖА ---")
    print(f"РЕЖИМ: {'ТЕСТОВЫЙ' if IS_TEST == 1 else 'БОЕВОЙ'}")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print(f"URL ДЛЯ ЗАПРОСА: {url}")
    print("----------------------------------------------------\n")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                text_response = (await response.text()).lstrip('\ufeff')
                print(f"[ROBOKASSA LOG] ПОЛУЧЕН ОТВЕТ (RAW XML):\n{text_response}\n")

                if response.status != 200:
                    print(f"[ROBOKASSA LOG] ОШИБКА: Robokassa вернула HTTP статус {response.status}")
                    return False

                root = ET.fromstring(text_response)
                namespace = {'ns': 'http://merchant.roboxchange.com/WebService/'}
                
                result_code_element = root.find("ns:Result/ns:Code", namespace)
                if result_code_element is None or result_code_element.text != '0':
                    error_desc_element = root.find("ns:Result/ns:Description", namespace)
                    error_desc = error_desc_element.text if error_desc_element is not None else "Нет описания"
                    print(f"[ROBOKASSA LOG] ОШИБКА В ОТВЕТЕ: Код {result_code_element.text if result_code_element is not None else 'N/A'} - {error_desc}")
                    return False

                state_code_element = root.find("ns:State/ns:Code", namespace)
                if state_code_element is not None and state_code_element.text == '100':
                    print("[ROBOKASSA LOG] УСПЕХ: Платеж подтвержден (код 100).")
                    return True
                else:
                    status_code = state_code_element.text if state_code_element is not None else 'N/A'
                    print(f"[ROBOKASSA LOG] ИНФО: Платеж еще не подтвержден. Текущий код статуса: {status_code}")
                    return False
        except Exception as e:
            print(f"[ROBOKASSA LOG] КРИТИЧЕСКАЯ ОШИБКА при запросе/парсинге: {e}")
            return False