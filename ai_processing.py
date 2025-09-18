# ai_processing.py

import asyncio
import google.generativeai as genai
import os
from config import GEMINI_API_KEYS

async def get_ai_review(prompt_template: str, task_text: str, audio_file_path: str) -> str:
    """
    Генерирует рецензию от AI, НАПРЯМУЮ АНАЛИЗИРУЯ АУДИОФАЙЛ.
    """
    prompt = prompt_template.format(task_text=task_text, user_text="[АУДИООТВЕТ УЧЕНИКА ПРИКРЕПЛЕН К ЗАПРОСУ]")
    
    for api_key in GEMINI_API_KEYS:
        try:
            genai.configure(api_key=api_key)
            
            # Шаг 1: Загружаем аудиофайл в Gemini
            print(f"Загрузка файла {audio_file_path} в Google AI...")
            audio_file = await genai.upload_file_async(path=audio_file_path)
            print("Файл успешно загружен.")

            # Шаг 2: Создаем модель и отправляем промпт вместе с аудиофайлом
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            print(f"Попытка использовать API ключ, который заканчивается на ...{api_key[-4:]}")
            response = await model.generate_content_async([prompt, audio_file])
            print("Запрос к Gemini API с аудиофайлом успешен.")

            # Шаг 3: Удаляем загруженный файл из хранилища Google
            await genai.delete_file_async(name=audio_file.name)
            print(f"Временный файл {audio_file.name} удален из Google AI.")

            return response.text
        
        except Exception as e:
            print(f"Ошибка с ключом ...{api_key[-4:]}: {e}")
            continue
            
    print("Все API ключи не сработали.")
    return "Бот сейчас перегружен. Пожалуйста, попробуйте еще раз через несколько минут."