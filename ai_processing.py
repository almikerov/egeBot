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
            
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            # Используем стандартную функцию upload_file внутри run_in_executor,
            # чтобы она выполнялась в отдельном потоке и не блокировала бота.
            
            print(f"Загрузка файла {audio_file_path} в Google AI...")
            loop = asyncio.get_running_loop()
            
            # genai.upload_file - это правильная функция для загрузки
            audio_file = await loop.run_in_executor(
                None, 
                lambda: genai.upload_file(path=audio_file_path)
            )
            print("Файл успешно загружен.")
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            model = genai.GenerativeModel('gemini-1.5-flash')
            
            print(f"Попытка использовать API ключ, который заканчивается на ...{api_key[-4:]}")
            response = await model.generate_content_async([prompt, audio_file])
            print("Запрос к Gemini API с аудиофайлом успешен.")

            # Удаление файла также делаем неблокирующим способом
            await loop.run_in_executor(
                None,
                lambda: genai.delete_file(name=audio_file.name)
            )
            print(f"Временный файл {audio_file.name} удален из Google AI.")

            return response.text
        
        except Exception as e:
            print(f"Ошибка с ключом ...{api_key[-4:]}: {e}")
            continue
            
    print("Все API ключи не сработали.")
    return "Бот сейчас перегружен. Пожалуйста, попробуйте еще раз через несколько минут."