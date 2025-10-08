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
IS_TEST = 1 

def generate_payment_link(user_id: int, amount: int, invoice_id: int) -> str:
    """Генерирует ссылку на оплату, используя правильные пароли."""
    description = "Подписка на AI-репетитора"
    
    password = ROBOKASSA_TEST_PASSWORD_1 if IS_TEST == 1 else ROBOKASSA_PASSWORD_1
    
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
    """Проверяет статус оплаты счёта и логирует полный ответ."""
    
    password = ROBOKASSA_TEST_PASSWORD_2 if IS_TEST == 1 else ROBOKASSA_PASSWORD_2
    
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    url = (f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
           f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
           f"InvoiceID={invoice_id}&"
           f"Signature={signature_hash}&"
           f"IsTest={IS_TEST}")
           
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text_response = await response.text()
                    
                    # --- УЛУЧШЕННОЕ ЛОГИРОВАНИЕ ---
                    print("="*50)
                    print(f"НАЧАЛО ОТВЕТА ОТ ROBOKASSA ДЛЯ СЧЕТА #{invoice_id}")
                    print(text_response)
                    print("КОНЕЦ ОТВЕТА ОТ ROBOKASSA")
                    print("="*50)
                    # --------------------------------

                    try:
                        root = ET.fromstring(text_response)
                        
                        # Ищем код результата операции
                        result_code = root.find(".//Result/Code")
                        if result_code is not None and int(result_code.text) != 0:
                            error_description = root.find(".//Result/Description").text
                            print(f"ОШИБКА ОТ ROBOKASSA: Код {result_code.text} - {error_description}")
                            return False

                        # Если ошибки нет, ищем статус платежа
                        state_code_element = root.find(".//State/Code")
                        if state_code_element is not None and state_code_element.text == '100':
                            print("Платеж подтвержден (код 100).")
                            return True
                        else:
                            status_text = state_code_element.text if state_code_element is not None else 'не найден'
                            print(f"Платеж НЕ подтвержден. Текущий статус: {status_text}")
                            return False

                    except ET.ParseError as e:
                        print(f"Критическая ошибка: Не удалось распарсить XML от Robokassa: {e}")
                        return False
                else:
                    print(f"Критическая ошибка: Robokassa вернула статус {response.status}")
                    return False
        except Exception as e:
            print(f"Критическая ошибка: Исключение при запросе к Robokassa: {e}")
            return False
            
    return False