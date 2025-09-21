# google_sheets_api.py

import random
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import GOOGLE_API_KEY, SPREADSHEET_ID

API_SERVICE_NAME = 'sheets'
API_VERSION = 'v4'

def get_sheets_service():
    """Инициализирует и возвращает сервис для работы с Google Sheets API, используя API-ключ."""
    try:
        service = build(API_SERVICE_NAME, API_VERSION, developerKey=GOOGLE_API_KEY, static_discovery=False)
        return service
    except Exception as e:
        print(f"ОШИБКА: Не удалось инициализировать сервис Google Sheets. Проверьте ваш GOOGLE_API_KEY. Ошибка: {e}")
        return None

async def get_sheet_titles() -> list:
    """Асинхронно получает список названий всех листов, которые начинаются на '()'."""
    service = get_sheets_service()
    if not service:
        return []
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')

        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        # Теперь выбираем ТОЛЬКО те листы, названия которых начинаются на "()"
        titles = [
            sheet['properties']['title'] for sheet in sheets
            if sheet['properties']['title'].startswith('()')
        ]
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

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
            range=f"'{sheet_title}'!A1:E"
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return None, None

        prompt = values[0][0] if values and values[0] else "Промпт не найден."
        tasks = values[2:]
        if not tasks:
            return prompt, None

        valid_tasks = [row for row in tasks if len(row) >= 3 and row[0] and row[2]]
        if not valid_tasks:
            return prompt, None
            
        random_task_row = random.choice(valid_tasks)
        
        task_data = {
            'id': random_task_row[0],
            'time_limit': int(random_task_row[1]) if len(random_task_row) > 1 and random_task_row[1].isdigit() else None,
            'task_text': random_task_row[2],
            'image1': random_task_row[3] if len(random_task_row) > 3 and random_task_row[3] else None,
            'image2': random_task_row[4] if len(random_task_row) > 4 and random_task_row[4] else None
        }
        
        return prompt, task_data

    except HttpError as err:
        print(f"Ошибка при получении задания с листа '{sheet_title}': {err}")
        return None, None

async def get_task_by_id(task_id: str) -> tuple:
    """
    Асинхронно ищет задание по ID по всем доступным листам.
    Возвращает (prompt, task_data) или (None, None) если не найдено.
    """
    service = get_sheets_service()
    if not service:
        return None, None
        
    sheet_titles = await get_sheet_titles()
    if not sheet_titles:
        return None, None

    for title in sheet_titles:
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{title}'!A1:E"
            ).execute()
            
            values = result.get('values', [])
            if not values:
                continue

            prompt = values[0][0] if values and values[0] else "Промпт не найден."
            tasks = values[2:]
            
            for row in tasks:
                if len(row) > 0 and row[0] == task_id:
                    task_data = {
                        'id': row[0],
                        'time_limit': int(row[1]) if len(row) > 1 and row[1].isdigit() else None,
                        'task_text': row[2] if len(row) > 2 else "Текст задания отсутствует.",
                        'image1': row[3] if len(row) > 3 and row[3] else None,
                        'image2': row[4] if len(row) > 4 and row[4] else None
                    }
                    return prompt, task_data
                    
        except HttpError as err:
            print(f"Ошибка при поиске на листе '{title}': {err}")
            continue
            
    return None, None