# task_manager.py

import pandas as pd
import random
from typing import List, Dict, Optional, Tuple

TASKS_FILE = 'tasks.xlsx'
tasks_data = {}

def clean_header(header):
    """Очищает заголовок от скобок и лишних пробелов."""
    if isinstance(header, str):
        return header.replace('{', '').replace('}', '').strip()
    return header

def load_tasks():
    """Загружает задания из всех листов локального Excel-файла."""
    global tasks_data
    try:
        xls = pd.ExcelFile(TASKS_FILE)
        tasks_data.clear()

        for sheet_name in xls.sheet_names:
            try:
                # Читаем промпт из самой первой ячейки (A1)
                prompt_df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=1)
                prompt = prompt_df.iloc[0, 0] if not prompt_df.empty else "Промпт не найден."

                # Читаем данные, используя вторую строку (индекс 1) как заголовки
                df = pd.read_excel(xls, sheet_name=sheet_name, header=1, dtype=str)
                
                # ОЧИЩАЕМ ЗАГОЛОВКИ ОТ СКОБОК
                df.columns = [clean_header(col) for col in df.columns]
                
                # Проверяем наличие обязательного столбца после очистки
                if 'task_text' not in df.columns:
                    print(f"ПРЕДУПРЕЖДЕНИЕ: На листе '{sheet_name}' не найден столбец 'task_text'. Пропускаем лист.")
                    continue
                
                # Переименовываем 'time' в 'time_limit' для совместимости
                if 'time' in df.columns:
                    df = df.rename(columns={'time': 'time_limit'})

                df = df.where(pd.notna(df), None)
                tasks_data[sheet_name] = {"prompt": prompt, "tasks": df.to_dict('records')}
            
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
    
    prompt = category.get("prompt")
    # Убедимся, что time_limit - это число
    tasks = []
    for task in category["tasks"]:
        time_limit_str = task.get('time_limit')
        if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit():
            task['time_limit'] = int(float(time_limit_str))
        else:
            task['time_limit'] = None
        tasks.append(task)

    random_task = random.choice(tasks)
    return prompt, random_task

def get_task_by_id(task_id: str) -> Optional[Tuple[str, Dict]]:
    for category_data in tasks_data.values():
        prompt = category_data.get("prompt")
        for task in category_data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                # Также обработаем time_limit на всякий случай
                time_limit_str = task.get('time_limit')
                if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit():
                    task['time_limit'] = int(float(time_limit_str))
                else:
                    task['time_limit'] = None
                return prompt, task
    return None, None

# Загружаем задания один раз при старте бота
load_tasks()