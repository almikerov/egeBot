# task_manager.py

import pandas as pd
import random
from typing import List, Dict, Optional, Tuple

TASKS_FILE = 'tasks.xlsx'
tasks_data = {}

def load_tasks():
    """Загружает задания из всех листов локального Excel-файла."""
    global tasks_data
    try:
        xls = pd.ExcelFile(TASKS_FILE)
        tasks_data.clear()

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=1, dtype=str)
            prompt_df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=1)
            prompt = prompt_df.iloc[0, 0] if not prompt_df.empty else "Промпт не найден."

            df = df.where(pd.notna(df), None)
            task_type = sheet_name
            tasks_data[task_type] = {
                "prompt": prompt,
                "tasks": []
            }

            tasks_list = df.to_dict('records')

            for task in tasks_list:
                time_limit_str = task.get('time_limit')
                task['time_limit'] = int(float(time_limit_str)) if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit() else None
                tasks_data[task_type]['tasks'].append(task)

        print(f"Файл с заданиями ({TASKS_FILE}) успешно загружен. Найдено листов: {len(tasks_data)}.")

    except FileNotFoundError:
        print(f"ОШИБКА: Файл с заданиями '{TASKS_FILE}' не найден.")
        tasks_data = {}
    except Exception as e:
        print(f"ОШИБКА: Не удалось прочитать файл '{TASKS_FILE}'. Проверьте структуру. Ошибка: {e}")
        tasks_data = {}

def get_task_types() -> List[str]:
    return list(tasks_data.keys())

def get_random_task(task_type: str) -> Optional[Tuple[str, Dict]]:
    category = tasks_data.get(task_type)
    if not category or not category.get("tasks"):
        return None, None
    prompt = category.get("prompt")
    random_task = random.choice(category["tasks"])
    return prompt, random_task

def get_task_by_id(task_id: str) -> Optional[Tuple[str, Dict]]:
    for category_data in tasks_data.values():
        prompt = category_data.get("prompt")
        for task in category_data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                return prompt, task
    return None, None

load_tasks()