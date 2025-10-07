# task_manager.py

import pandas as pd
import yaml
import random
from typing import List, Dict, Optional, Tuple

TASKS_FILE = 'tasks.xlsx'
PROMPTS_FILE = 'prompts.yml'
tasks_data = {}
prompts_data = {}

def clean_header(header):
    if isinstance(header, str):
        return header.replace('{', '').replace('}', '').strip()
    return header

def load_data():
    """Загружает задания и промпты из файлов."""
    global tasks_data, prompts_data
    
    # Загрузка промптов
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompts_data = yaml.safe_load(f)
        print(f"Файл с промптами ({PROMPTS_FILE}) успешно загружен.")
    except FileNotFoundError:
        print(f"ОШИБКА: Файл с промптами '{PROMPTS_FILE}' не найден.")
        prompts_data = {}
    except Exception as e:
        print(f"ОШИБКА: Не удалось прочитать файл '{PROMPTS_FILE}'. Ошибка: {e}")
        prompts_data = {}

    # Загрузка заданий
    try:
        xls = pd.ExcelFile(TASKS_FILE)
        tasks_data.clear()

        for sheet_name in xls.sheet_names:
            try:
                # Теперь читаем заголовки из ПЕРВОЙ строки (header=0)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=0, dtype=str)
                df.columns = [clean_header(col) for col in df.columns]
                
                if 'task_text' not in df.columns:
                    print(f"ПРЕДУПРЕЖДЕНИЕ: На листе '{sheet_name}' не найден столбец 'task_text'. Пропускаем лист.")
                    continue
                
                if 'time' in df.columns:
                    df = df.rename(columns={'time': 'time_limit'})

                df = df.where(pd.notna(df), None)
                tasks_data[sheet_name] = {"tasks": df.to_dict('records')}
            
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
    prompt = prompts_data.get(task_type, "Промпт не найден.")
    
    if not category or not category.get("tasks"):
        return prompt, None
    
    tasks = []
    for task in category["tasks"]:
        time_limit_str = task.get('time_limit')
        task['time_limit'] = int(float(time_limit_str)) if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit() else None
        tasks.append(task)

    random_task = random.choice(tasks)
    return prompt, random_task

def get_task_by_id(task_id: str) -> Optional[Tuple[str, Dict]]:
    for task_type, category_data in tasks_data.items():
        prompt = prompts_data.get(task_type, "Промпт не найден.")
        for task in category_data.get("tasks", []):
            if str(task.get("id")) == str(task_id):
                time_limit_str = task.get('time_limit')
                task['time_limit'] = int(float(time_limit_str)) if time_limit_str and str(time_limit_str).replace('.', '', 1).isdigit() else None
                return prompt, task
    return None, None

def get_prompt(task_type: str) -> str:
    return prompts_data.get(task_type, "Промпт для этого типа не найден.")

def save_prompt(task_type: str, new_text: str):
    prompts_data[task_type] = new_text
    try:
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(prompts_data, f, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения промпта: {e}")
        return False

# Загружаем данные один раз при старте бота
load_data()