# ai_processing.py

import asyncio
import whisper
import google.generativeai as genai
from pydub import AudioSegment
from config import GEMINI_API_KEYS
from prompt_manager import load_prompt

print("Загрузка модели Whisper... (это может занять несколько минут)")
whisper_model = whisper.load_model("base")
print("Модель Whisper успешно загружена.")

async def recognize_speech(ogg_audio_path: str) -> str:
    try:
        mp3_audio_path = ogg_audio_path.replace(".ogg", ".mp3")
        audio = AudioSegment.from_ogg(ogg_audio_path)
        audio.export(mp3_audio_path, format="mp3")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: whisper_model.transcribe(mp3_audio_path))
        recognized_text = result.get("text", "Текст не распознан.")
        return recognized_text
    except Exception as e:
        print(f"Ошибка при распознавании речи: {e}")
        return "Ошибка: не удалось распознать речь."

async def get_ai_review(task_text: str, user_text: str) -> str:
    base_prompt = load_prompt()
    prompt = base_prompt.format(task_text=task_text, user_text=user_text)
    
    for api_key in GEMINI_API_KEYS:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            print(f"Попытка использовать API ключ, который заканчивается на ...{api_key[-4:]}")
            response = await model.generate_content_async(prompt)
            print("Запрос к Gemini API успешен.")
            return response.text
        
        except Exception as e:
            print(f"Ошибка с ключом ...{api_key[-4:]}: {e}")
            continue
            
    print("Все API ключи не сработали.")
    return "Бот сейчас перегружен. Пожалуйста, попробуйте еще раз через несколько минут."