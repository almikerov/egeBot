# ai_processing.py

import asyncio
import whisper
import google.generativeai as genai
from pydub import AudioSegment
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

print("Загрузка модели Whisper... (это может занять несколько минут)")
whisper_model = whisper.load_model("base")
print("Модель Whisper успешно загружена.")

def get_prompt_from_file():
    try:
        with open("prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Произошла ошибка: файл prompt.txt не найден."

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
    model = genai.GenerativeModel('gemini-1.5-flash')
    base_prompt = get_prompt_from_file()
    prompt = base_prompt.format(task_text=task_text, user_text=user_text)
    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        print(f"Произошла ошибка при обращении к Gemini API: {e}")
        return "К сожалению, не удалось получить рецензию от AI. Попробуйте позже."