# task_manager.py

import pandas as pd
import random
from typing import List, Dict, Optional, Tuple

TASKS_FILE = 'tasks.xlsx'
tasks_data = {}

def clean_header(header):
    if isinstance(header, str):
        return header.replace('{', '').replace('}', '').strip()
    return header

def load_data():
    """Загружает задания и промпты из файла tasks.xlsx."""
    global tasks_data
    
    try:
        xls = pd.ExcelFile(TASKS_FILE)
        tasks_data.clear()

        for sheet_name in xls.sheet_names:
            try:
                # Читаем первую строку для получения промпта
                prompt_df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=1)
                prompt = prompt_df.iloc[0, 0] if not prompt_df.empty else "Промпт не найден."

                # Теперь читаем заголовки из ВТОРОЙ строки (header=1)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=1, dtype=str)
                df.columns = [clean_header(col) for col in df.columns]
                
                if 'task_text' not in df.columns:
                    print(f"ПРЕДУПРЕЖДЕНИЕ: На листе '{sheet_name}' не найден столбец 'task_text'. Пропускаем лист.")
                    continue
                
                if 'time' in df.columns:
                    df = df.rename(columns={'time': 'time_limit'})

                df = df.where(pd.notna(df), None)
                tasks_data[sheet_name] = {"tasks": df.to_dict('records'), "prompt": prompt}
            
            except Exception as e:
                print(f"ОШИБКА: Не удалось обработать лист '{sheet_name}'. Ошибка: {e}")
                continue

        print(f"Файл с заданиями ({TASKS_FILE}) успешно загружен. Обработано листов: {len(tasks_data)}.")

    except FileNotFoundError:
        print(f"ОШИБКА: Файл с заданиями '{TASKS_FILE}' не найден.")
    except Exception as e:
        print(f"ОШИБКА: Не удалось прочитать файл '{TASKS_FILE}'. Ошибка: {e}")

def get_task_types() -> List[str]:
    return list(tasks_data.keys())

def get_random_task(task_type: str) -> Optional[Tuple[str, Dict]]:
    category = tasks_data.get(task_type)
    if not category or not category.get("tasks"):
        return None, None
    
    prompt = category.get("prompt", "Промпт не найден.")
    tasks = []
    for task in category["tasks"]:
        time_limit_str = task.get('time_limit')
        task['time_limit'] = int(float(time_limit_str)) if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit() else None
        tasks.append(task)

    random_task = random.choice(tasks)
    return prompt, random_task

def get_task_by_id(task_id: str) -> Optional[Tuple[str, Dict]]:
    for task_type, category_data in tasks_data.items():
        prompt = category_data.get("prompt", "Промпт не найден.")
        for task in category_data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                time_limit_str = task.get('time_limit')
                task['time_limit'] = int(float(time_limit_str)) if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit() else None
                return prompt, task
    return None, None

# Загружаем данные один раз при старте бота
load_data()