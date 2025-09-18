# google_sheets_api.py

import random
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import GOOGLE_API_KEY

# --- Настройки ---
SPREADSHEET_ID = '1TSWXh7niTodEFoppkT8ojGkps0l8SvXQFUlwHm1DdMQ'
API_SERVICE_NAME = 'sheets'
API_VERSION = 'v4'

def get_sheets_service():
    """Инициализирует и возвращает сервис для работы с Google Sheets API, используя API-ключ."""
    try:
        service = build(API_SERVICE_NAME, API_VERSION, developerKey=GOOGLE_API_KEY)
        return service
    except Exception as e:
        print(f"ОШИБКА: Не удалось инициализировать сервис Google Sheets. Проверьте ваш GOOGLE_API_KEY. Ошибка: {e}")
        return None

async def get_sheet_titles() -> list:
    """Асинхронно получает список названий всех листов в таблице."""
    service = get_sheets_service()
    if not service:
        return []
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        titles = [sheet['properties']['title'] for sheet in sheets]
        return titles
    except HttpError as err:
        print(f"Ошибка при получении названий листов: {err}")
        return []

async def get_task_from_sheet(sheet_title: str) -> tuple:
    """
    Асинхронно получает промпт и случайное задание с указанного листа.
    Возвращает кортеж (prompt, task_data) или (None, None) в случае ошибки.
    """
    service = get_sheets_service()
    if not service:
        return None, None
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_title}'!A1:C"
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return None, None

        prompt = values[0][0] if values and values[0] else "Промпт не найден."
        tasks = values[2:]
        if not tasks:
            return prompt, None

        valid_tasks = [row for row in tasks if len(row) >= 2 and row[0] and row[1]]
        if not valid_tasks:
            return prompt, None
            
        random_task_row = random.choice(valid_tasks)
        
        task_data = {
            'id': random_task_row[0],
            'task_text': random_task_row[1],
            'image1': random_task_row[2] if len(random_task_row) > 2 and random_task_row[2] else None
        }
        
        return prompt, task_data

    except HttpError as err:
        print(f"Ошибка при получении задания с листа '{sheet_title}': {err}")
        return None, None