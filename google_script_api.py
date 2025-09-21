# google_script_api.py
import aiohttp
from config import GOOGLE_APP_SCRIPT_URL

async def get_sheet_titles() -> list:
    """Асинхронно получает список названий листов через вебхук Apps Script."""
    params = {'action': 'get_titles'}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(GOOGLE_APP_SCRIPT_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        return data.get('titles', [])
                print(f"Ошибка получения названий листов: {response.status}")
                return []
        except Exception as e:
            print(f"Исключение при получении названий листов: {e}")
            return []

async def get_task_from_sheet(sheet_title: str) -> tuple:
    """Асинхронно получает задание с листа через вебхук Apps Script."""
    params = {'action': 'get_task_from_sheet', 'sheet': sheet_title}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(GOOGLE_APP_SCRIPT_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        return data.get('prompt'), data.get('task_data')
                print(f"Ошибка получения задания с листа '{sheet_title}': {response.status}")
                return None, None
        except Exception as e:
            print(f"Исключение при получении задания с листа '{sheet_title}': {e}")
            return None, None

async def get_task_by_id(task_id: str) -> tuple:
    """Асинхронно ищет задание по ID через вебхук Apps Script."""
    params = {'action': 'get_task_by_id', 'id': task_id}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(GOOGLE_APP_SCRIPT_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        return data.get('prompt'), data.get('task_data')
                print(f"Ошибка поиска задания по ID '{task_id}': {response.status}")
                return None, None
        except Exception as e:
            print(f"Исключение при поиске задания по ID '{task_id}': {e}")
            return None, None