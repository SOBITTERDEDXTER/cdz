import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# ================= НАСТРОЙКИ =================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")# =============================================

# Инициализация ИИ
client = genai.Client(api_key=GEMINI_API_KEY)

# Временное хранилище токена МЭШ
user_tokens = {}

def solve_homework_with_ai(task_text):
    """Отправка задания в Gemini"""
    try:
        prompt = (
            "Ты — помощник по школьной программе. Реши задание из МЭШ. "
            "Дай чёткий, краткий и точный ответ. Если это тест с вариантами — укажи правильный вариант:\n\n"
            f"{task_text}"
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Ошибка ИИ: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я твой личный бот для МЭШ.\n\n"
        "1. Отправь мне свой Auth-Token из МЭШ.\n"
        "2. Напиши команду /dz, и я пришлю ответы на все актуальные домашние задания!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.chat_id
    
    # Если пользователь прислал токен (JWT начинается на eyJ...)
    if text.startswith("eyJ"):
        user_tokens[user_id] = text
        await update.message.reply_text("✅ Токен сохранен! Теперь напиши /dz чтобы получить ответы.")
    else:
        await update.message.reply_text("Чтобы сохранить токен МЭШ, отправь строку, начинающуюся с `eyJ...`")

async def get_dz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.message.reply_text("❌ Сначала отправь мне свой Auth-Token из МЭШ!")
        return

    await update.message.reply_text("🔍 Запрашиваю ДЗ из МЭШ и генерирую ответы...")

    headers = {
        "Auth-Token": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # Запрос к API МЭШ
    url = "https://school.mos.ru/api/family/web/v1/homeworks"
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            await update.message.reply_text(f"⚠️ Ошибка авторизации ({res.status_code}). Возможно, токен протух — скинь свежий!")
            return
            
        data = res.json()
        homeworks = data.get("payload", [])
        
        if not homeworks:
            await update.message.reply_text("🎉 Новых домашних заданий не найдено!")
            return

        for item in homeworks[:5]: # Берем первые 5 ДЗ
            subject = item.get("subject_name", "Предмет")
            description = item.get("description", "Без описания")
            
            if description and description != "Без описания":
                # Решаем через ИИ
                ai_answer = solve_homework_with_ai(description)
                
                msg = f"📘 *{subject}*\n📝 *Задание:* {description[:200]}...\n\n✅ *Ответ:* {ai_answer}"
                await update.message.reply_text(msg, parse_mode="Markdown")
                
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка при обработке: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dz", get_dz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен! Открой его в Telegram.")
    app.run_polling()
