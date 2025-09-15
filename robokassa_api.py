# robokassa_api.py

import hashlib
import aiohttp
from config import ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2

def generate_payment_link(user_id: int, amount: int, invoice_id: int) -> str:
    """Генерирует ссылку на оплату."""
    description = "Подписка на AI-репетитора на 1 месяц"
    
    # Формируем подпись для создания ссылки
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{amount}:{invoice_id}:{ROBOKASSA_PASSWORD_1}:shp_user={user_id}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    # Формируем URL
    link = (f"https://auth.robokassa.ru/Merchant/Index.aspx?"
            f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
            f"OutSum={amount}&"
            f"InvId={invoice_id}&"
            f"Description={description}&"
            f"SignatureValue={signature_hash}&"
            f"shp_user={user_id}&" # Дополнительный параметр для идентификации пользователя
            f"IsTest=1") # 1 - для тестов, 0 - для реальных платежей
            
    return link

async def check_payment(invoice_id: int) -> bool:
    """Проверяет статус оплаты счёта."""
    # Формируем подпись для проверки статуса
    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{ROBOKASSA_PASSWORD_2}"
    signature_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    # URL для запроса статуса (XML интерфейс)
    url = (f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
           f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
           f"InvoiceID={invoice_id}&"
           f"Signature={signature_hash}")
           
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text_response = await response.text()
                    # Ищем в XML ответе код состояния. 100 означает "оплачено"
                    if '<StateCode>100</StateCode>' in text_response:
                        return True
                else:
                    print(f"Ошибка проверки платежа Robokassa: {response.status}")
                    return False
        except Exception as e:
            print(f"Исключение при проверке платежа: {e}")
            return False
    return False