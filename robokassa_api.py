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
    Генерирует ссылку на оплату без shp_ параметров.
    """
    password_1, _ = _get_credentials()
    description = "Подписка на AI-репетитора"
    
    formatted_amount = f"{amount:.2f}"

    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{formatted_amount}:{invoice_id}:{password_1}"
    signature_hash = hashlib.md5(signature_str.encode("utf-8")).hexdigest()

    print("\n--- [ROBOKASSA LOG] ГЕНЕРАЦИЯ ССЫЛКИ ---")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print("---------------------------------------------------\n")

    link = (
        f"https://auth.robokassa.ru/Merchant/Index.aspx?"
        f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
        f"OutSum={formatted_amount}&"
        f"InvId={invoice_id}&"
        f"Description={description}&"
        f"SignatureValue={signature_hash}&"
        f"IsTest={IS_TEST}"
    )
    return link


async def check_payment(invoice_id: int) -> bool:
    """
    Проверяет статус оплаты через RoboKassa API (OpState).
    Возвращает True, если платеж прошел успешно (State=100).
    """
    _, password_2 = _get_credentials()

    signature_str = f"{ROBOKASSA_MERCHANT_LOGIN}:{invoice_id}:{password_2}"
    signature_hash = hashlib.md5(signature_str.encode("utf-8")).hexdigest()

    url = (
        f"https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState?"
        f"MerchantLogin={ROBOKASSA_MERCHANT_LOGIN}&"
        f"InvoiceID={invoice_id}&"
        f"Signature={signature_hash}&"
        f"IsTest={IS_TEST}"
    )

    print("\n--- [ROBOKASSA LOG] ПРОВЕРКА СТАТУСА ---")
    print(f"СТРОКА ДЛЯ ПОДПИСИ: {signature_str}")
    print(f"ПОДПИСЬ (MD5): {signature_hash}")
    print(f"URL ДЛЯ ЗАПРОСА: {url}")
    print("----------------------------------------------------\n")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                text_response = (await response.text()).lstrip("\ufeff")
                print(f"[ROBOKASSA LOG] ПОЛУЧЕН ОТВЕТ (RAW XML):\n{text_response}\n")

                if response.status != 200:
                    print(f"[ROBOKASSA LOG] Ошибка HTTP: {response.status}")
                    return False

                # Парсим XML
                root = ET.fromstring(text_response)
                namespace = {"ns": "http://merchant.roboxchange.com/WebService/"}

                # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
                # Ищем вложенные теги <Code> внутри <Result> и <State>
                result_code_element = root.find("ns:Result/ns:Code", namespace)
                state_code_element = root.find("ns:State/ns:Code", namespace)

                # Проверка кода результата
                if result_code_element is None:
                    print("[ROBOKASSA LOG] Ошибка: Тег <Result/Code> не найден.")
                    return False
                if result_code_element.text.strip() != "0":
                    print(f"[ROBOKASSA LOG] Ошибка: Result Code={result_code_element.text.strip()}")
                    return False

                # Проверка состояния платежа
                if state_code_element is None:
                    # Оставляем проверку на старый формат <StateCode> как запасной вариант
                    state_code_element = root.find("ns:StateCode", namespace)
                    if state_code_element is None:
                        print("[ROBOKASSA LOG] Ошибка: Тег <State/Code> или <StateCode> не найден.")
                        return False

                print(f"[ROBOKASSA LOG] State Code={state_code_element.text.strip()}")

                if state_code_element.text.strip() == "100":
                    print("[ROBOKASSA LOG] ✅ Платеж подтвержден (код 100).")
                    return True
                else:
                    print(f"[ROBOKASSA LOG] ❌ Платеж еще не завершен или отклонен (код {state_code_element.text.strip()}).")
                    return False
                # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        except Exception as e:
            print(f"[ROBOKASSA LOG] КРИТИЧЕСКАЯ ОШИБКА: {e}")
            return False