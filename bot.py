import os, requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, WebhookInfo

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_URL"]  # e.g. https://goose-bot.onrender.com
PORT = int(os.environ.get("PORT", 10000))

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": msg}]
            },
            timeout=60
        )
        reply = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        reply = f"Error: {e}"
    await update.message.reply_text(reply)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle))
app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    webhook_url=f"{RENDER_URL}/webhook"
)
