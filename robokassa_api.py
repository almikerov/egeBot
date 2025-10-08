# robokassa_api.py

import hashlib
import aiohttp
import xml.etree.ElementTree as ET # ИЗМЕНЕНО: Импортируем библиотеку для работы с XML
from config import ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2

def generate_payment_link(user_id: int, amount: int, invoice_id: int) -> str:
    """Генерирует ссылку на оплату."""
    description = "Подписка на AI-репетитора на 1 месяц"
    
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{ROBOKASSA_PASSWORD_1}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    link = (f"https://auth.robokassa.ru/Merchant/Index.aspx?"
            f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
            f"OutSum={amount}&"
            f"InvId={invoice_id}&"
            f"Description={description}&"
            f"SignatureValue={signature_hash}&"
            f"shp_user={user_id}&"
            f"IsTest=1") # Оставляем 1 для тестов
            
    return link

async def check_payment(invoice_id: int) -> bool:
    """Проверяет статус оплаты счёта."""
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{ROBOKASSA_PASSWORD_2}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    url = (f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
           f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
           f"InvoiceID={invoice_id}&"
           f"Signature={signature_hash}")
           
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text_response = await response.text()
                    # ИЗМЕНЕНО: Надежный парсинг XML вместо простого поиска строки
                    try:
                        root = ET.fromstring(text_response)
                        state_code_element = root.find(".//State/Code") # Ищем тег <Code> внутри <State>
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