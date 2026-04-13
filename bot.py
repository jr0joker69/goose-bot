import os, subprocess, requests, re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ.get("RENDER_URL", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
PORT = int(os.environ.get("PORT", 10000))

history = {}

SYSTEM = """You are a powerful coding agent on a Linux server. You can:
1. Run shell commands: <RUN>command</RUN>
2. Write files: <FILE name="filename.js">content</FILE>
3. Deploy Cloudflare Workers: <DEPLOY name="worker-name">js code</DEPLOY>
Think step by step. Always explain what you are doing."""

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = result.stdout + result.stderr
        return out[:2000] if out else "Done (no output)"
    except subprocess.TimeoutExpired:
        return "Timeout after 30s"
    except Exception as e:
        return f"Error: {e}"

def write_file(name, content):
    try:
        with open(name, "w") as f:
            f.write(content)
        return f"Written: {name}"
    except Exception as e:
        return f"Error: {e}"

def deploy_worker(name, code):
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        return "Missing CF_API_TOKEN or CF_ACCOUNT_ID"
    try:
        r = requests.put(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/workers/scripts/{name}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/javascript"},
            data=code
        )
        data = r.json()
        if data.get("success"):
            return f"Deployed: https://{name}.{CF_ACCOUNT_ID}.workers.dev"
        return f"Failed: {data.get('errors')}"
    except Exception as e:
        return f"Error: {e}"

def process_actions(text):
    results = []
    for match in re.finditer(r'<RUN>(.*?)</RUN>', text, re.DOTALL):
        cmd = match.group(1).strip()
        results.append(f"$ {cmd}\n{run_command(cmd)}")
    for match in re.finditer(r'<FILE name="([^"]+)">(.*?)</FILE>', text, re.DOTALL):
        results.append(write_file(match.group(1), match.group(2).strip()))
    for match in re.finditer(r'<DEPLOY name="([^"]+)">(.*?)</DEPLOY>', text, re.DOTALL):
        results.append(deploy_worker(match.group(1), match.group(2).strip()))
    return "\n\n".join(results) if results else None

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    msg = update.message.text
    if uid not in history:
        history[uid] = []
    history[uid].append({"role": "user", "content": msg})
    if len(history[uid]) > 20:
        history[uid] = history[uid][-20:]
    await update.message.reply_text("⚙️ Thinking...")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": SYSTEM}] + history[uid],
                "temperature": 0.7,
                "max_tokens": 2048
            },
            timeout=60
        )
        reply = r.json()["choices"][0]["message"]["content"]
        history[uid].append({"role": "assistant", "content": reply})
        action_output = process_actions(reply)
        for chunk in [reply[i:i+4000] for i in range(0, len(reply), 4000)]:
            await update.message.reply_text(chunk)
        if action_output:
            await update.message.reply_text(f"📟 Output:\n{action_output}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def start(update, ctx):
    await update.message.reply_text("🦆 Goose Agent ready\nSend me anything to build.")

async def clear(update, ctx):
    history.pop(update.message.chat_id, None)
    await update.message.reply_text("Memory cleared.")

async def run(update, ctx):
    cmd = " ".join(ctx.args)
    if cmd:
        await update.message.reply_text(f"$ {cmd}\n{run_command(cmd)}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("clear", clear))
app.add_handler(CommandHandler("run", run))
app.add_handler(MessageHandler(filters.TEXT, handle))

if RENDER_URL:
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path="/webhook", webhook_url=f"{RENDER_URL}/webhook")
else:
    app.run_polling(drop_pending_updates=True)
