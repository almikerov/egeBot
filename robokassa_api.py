# robokassa_api.py

import hashlib
import aiohttp
import xml.etree.ElementTree as ET
from config import ROBOKASSA_MERCHANT_LOGIN

# --- ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА ---
# 1 = Тестовый режим, 0 = Боевой режим
# Устанавливаем тестовый режим, как вы и просили.
IS_TEST = 1

def generate_payment_link(user_id: int, amount: int, invoice_id: int, password_1: str) -> str:
    """
    Генерирует ссылку на оплату с правильной подписью.
    Принимает все необходимые данные как аргументы.
    """
    description = "Подписка на AI-репетитора"

    # Формируем строку для подписи. Все shp_ параметры должны быть включены.
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{password_1}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    print("\n--- ГЕНЕРАЦИЯ ССЫЛКИ НА ОПЛАТУ ---")
    print(f"ЛОГИН: {ROBOKASSA_MERCHANT_LOGIN}")
    print(f"СУММА: {amount}")
    print(f"НОМЕР СЧЕТА: {invoice_id}")
    print(f"ПАРОЛЬ #1: ...{password_1[-4:]}")
    print(f"shp_user: {user_id}")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print("-------------------------------------\n")

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
    Принимает все необходимые данные как аргументы.
    """
    # Формируем строку для подписи. Все shp_ параметры, которые были при создании, должны быть и здесь.
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password_2}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

    url = (
        f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
        f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
        f"InvoiceID={invoice_id}&"
        f"Signature={signature_hash}"
    )

    print("\n--- ПРОВЕРКА СТАТУСА ПЛАТЕЖА ---")
    print(f"ЛОГИН: {ROBOKASSA_MERCHANT_LOGIN}")
    print(f"НОМЕР СЧЕТА: {invoice_id}")
    print(f"ПАРОЛЬ #2: ...{password_2[-4:]}")
    print(f"shp_user: {user_id}")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print(f"URL ДЛЯ ЗАПРОСА: {url}")
    print("------------------------------------\n")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                text_response = (await response.text()).lstrip('\ufeff')
                print(f"ПОЛУЧЕН ОТВЕТ ОТ ROBOKASSA (RAW XML):\n{text_response}\n")

                if response.status != 200:
                    print(f"ОШИБКА: Robokassa вернула статус {response.status}")
                    return False

                root = ET.fromstring(text_response)
                namespace = {'ns': 'http://merchant.roboxchange.com/WebService/'}
                
                result_code_element = root.find("ns:Result/ns:Code", namespace)
                if result_code_element is None or result_code_element.text != '0':
                    error_desc = root.find("ns:Result/ns:Description", namespace).text
                    print(f"ОШИБКА В ОТВЕТЕ ROBOKASSA: Код {result_code_element.text if result_code_element is not None else 'N/A'} - {error_desc}")
                    return False

                state_code_element = root.find("ns:State/ns:Code", namespace)
                if state_code_element is not None and state_code_element.text == '100':
                    print("УСПЕХ: Платеж подтвержден (код 100).")
                    return True
                else:
                    print(f"ИНФО: Платеж еще не подтвержден. Код статуса: {state_code_element.text if state_code_element is not None else 'N/A'}")
                    return False
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА при проверке платежа: {e}")
            return False