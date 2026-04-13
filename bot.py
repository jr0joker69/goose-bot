import os, requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

GOOSE_URL = "http://localhost:3000"
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    try:
        r = requests.post(
            f"{GOOSE_URL}/api/v1/reply",
            json={"messages": [{"role": "user", "content": msg}]},
            timeout=60
        )
        data = r.json()
        # try multiple possible response keys
        reply = (
            data.get("content") or
            data.get("response") or
            data.get("message") or
            str(data)
        )
    except Exception as e:
        reply = f"Error: {e}"
    await update.message.reply_text(reply)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle))
app.run_polling()
