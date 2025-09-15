# prompt_manager.py

import os

PROMPT_FILE = 'prompt.txt'
DEFAULT_PROMPT = """Выступи в роли строгого, но справедливого эксперта ЕГЭ по английскому языку.
Проанализируй ответ ученика на следующее задание и дай развернутую рецензию.
**Задание:** "{task_text}"
**Ответ ученика (распознанный текст):** "{user_text}"

**Формат ответа:**
- **Общая оценка:** Краткое резюме.
- **✅ Сильные стороны:** Что получилось хорошо.
- **⚠️ Точки роста:** Что можно улучшить.
- **❌ Ошибки и рекомендации:** Конкретные примеры ошибок с исправлениями."""

def load_prompt():
    """Загружает промпт из файла. Если файл не найден, создает его с текстом по умолчанию."""
    if not os.path.exists(PROMPT_FILE):
        save_prompt(DEFAULT_PROMPT)
        return DEFAULT_PROMPT
    
    try:
        with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        save_prompt(DEFAULT_PROMPT)
        return DEFAULT_PROMPT

def save_prompt(prompt_text):
    """Сохраняет текст промпта в файл."""
    with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(prompt_text)