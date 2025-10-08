# robokassa_api.py

import hashlib
import aiohttp
import xml.etree.ElementTree as ET
from config import (
    ROBOKASSA_MERCHANT_LOGIN, 
    ROBOKASSA_PASSWORD_1, 
    ROBOKASSA_PASSWORD_2,
    ROBOKASSA_TEST_PASSWORD_1,
    ROBOKASSA_TEST_PASSWORD_2
)

# --- ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА ---
# 1 = Тестовый режим, 0 = Боевой режим
IS_TEST = 0 

def generate_payment_link(user_id: int, amount: int, invoice_id: int) -> str:
    """Генерирует ссылку на оплату, используя правильные пароли."""
    description = "Подписка на AI-репетитора"
    
    password = ROBOKASSA_TEST_PASSWORD_1 if IS_TEST == 1 else ROBOKASSA_PASSWORD_1
    
    # --- ОТЛАДКА ---
    print("\n--- ДАННЫЕ ДЛЯ СОЗДАНИЯ ССЫЛКИ ---")
    print(f"MerchantLogin: '{ROBOKASSA_MERCHANT_LOGIN}'")
    print(f"Пароль #1 (используется): '{password[:4]}...{password[-4:]}'")
    print("---------------------------------\n")

    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{password}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    link = (f"https://auth.robokassa.ru/Merchant/Index.aspx?"
            f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
            f"OutSum={amount}&"
            f"InvId={invoice_id}&"
            f"Description={description}&"
            f"SignatureValue={signature_hash}&"
            f"shp_user={user_id}&"
            f"IsTest={IS_TEST}")
            
    return link

async def check_payment(invoice_id: int) -> bool:
    """Проверяет статус оплаты счёта и логирует абсолютно всё."""
    
    password = ROBOKASSA_TEST_PASSWORD_2 if IS_TEST == 1 else ROBOKASSA_PASSWORD_2
    
    # --- ОТЛАДКА ---
    print("\n--- ДАННЫЕ ДЛЯ ПРОВЕРКИ ПЛАТЕЖА ---")
    print(f"MerchantLogin: '{ROBOKASSA_MERCHANT_LOGIN}'")
    print(f"Пароль #2 (используется): '{password[:4]}...{password[-4:]}'")
    print(f"InvoiceID для проверки: {invoice_id}")
    print("------------------------------------\n")

    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    url = (f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
           f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
           f"InvoiceID={invoice_id}&"
           f"Signature={signature_hash}&"
           f"IsTest={IS_TEST}")
    
    # --- ОТЛАДКА ---
    print(f"URL ДЛЯ ЗАПРОСА ПРОВЕРКИ:\n{url}\n")
           
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                text_response = (await response.text()).lstrip('\ufeff')
                print(f"ПОЛУЧЕН ОТВЕТ ОТ ROBOKASSA:\n{text_response}\n")
                
                # ... остальной код парсинга ...
                if response.status == 200:
                    try:
                        root = ET.fromstring(text_response)
                        namespace = {'ns': 'http://merchant.roboxchange.com/WebService/'}
                        result_code_element = root.find("ns:Result/ns:Code", namespace)
                        if result_code_element is not None and result_code_element.text != '0':
                            error_desc = root.find("ns:Result/ns:Description", namespace).text
                            print(f"ОШИБКА ОТ ROBOKASSA: Код {result_code_element.text} - {error_desc}")
                            return False
                        state_code_element = root.find("ns:State/ns:Code", namespace)
                        if state_code_element is not None and state_code_element.text == '100':
                            print("УСПЕХ: Платеж подтвержден (код 100).")
                            return True
                    except Exception as e:
                        print(f"Критическая ошибка парсинга XML: {e}")
                return False
        except Exception as e:
            print(f"Критическая ошибка сети: {e}")
            return False
    return False