# robokassa_api.py

import hashlib
import aiohttp
import xml.etree.ElementTree as ET
from config import ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2

# --- НАСТРОЙКА РЕЖИМА ---
# Измените на 0, когда будете готовы принимать реальные платежи
IS_TEST = 1 

def generate_payment_link(user_id: int, amount: int, invoice_id: int) -> str:
    """Генерирует ссылку на оплату."""
    description = "Подписка на AI-репетитора"
    
    # Для тестового режима используются тестовые пароли из ЛК Robokassa
    password = ROBOKASSA_PASSWORD_1 
    
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{password}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    link = (f"https://auth.robokassa.ru/Merchant/Index.aspx?"
            f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
            f"OutSum={amount}&"
            f"InvId={invoice_id}&"
            f"Description={description}&"
            f"SignatureValue={signature_hash}&"
            f"shp_user={user_id}&"
            f"IsTest={IS_TEST}") # Используем переменную
            
    return link

async def check_payment(invoice_id: int) -> bool:
    """Проверяет статус оплаты счёта."""
    
    # Для тестового режима используются тестовые пароли из ЛК Robokassa
    password = ROBOKASSA_PASSWORD_2
    
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    # ИЗМЕНЕНО: Добавлен параметр IsTest=1 для корректной проверки тестовых платежей
    url = (f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
           f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
           f"InvoiceID={invoice_id}&"
           f"Signature={signature_hash}&"
           f"IsTest={IS_TEST}") # Используем переменную
           
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text_response = await response.text()
                    try:
                        root = ET.fromstring(text_response)
                        state_code_element = root.find(".//State/Code")
                        # Код 100 для успешного тестового платежа, 101 для реального в процессе
                        if state_code_element is not None and state_code_element.text == '100':
                            return True
                    except ET.ParseError as e:
                        print(f"Ошибка парсинга XML от Robokassa: {e}")
                        return False
                else:
                    print(f"Ошибка проверки платежа Robokassa: {response.status}")
                    return False
        except Exception as e:
            print(f"Исключение при проверке платежа: {e}")
            return False
    return False