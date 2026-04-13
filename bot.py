import os, subprocess, requests, json, re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ.get("RENDER_URL", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
PORT = int(os.environ.get("PORT", 10000))

history = {}

SYSTEM = """You are a powerful coding agent running on a Linux server. You can:
1. Run shell commands by wrapping them in <RUN>command here</RUN>
2. Write files by wrapping in <FILE name="filename.js">content</FILE>
3. Deploy Cloudflare Workers by wrapping JS in <DEPLOY name="worker-name">js code</DEPLOY>

Rules:
- Think step by step before acting
- For code tasks: write the code, run it, fix errors
- For Cloudflare Workers: write clean JS with proper fetch handler
- Always explain what you are doing
- Return command output after running
"""

def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=30
        )
        out = result.stdout + result.stderr
        return out[:2000] if out else "Done (no output)"
    except subprocess.TimeoutExpired:
        return "Timeout after 30s"
    except Exception as e:
        return f"Error: {e}"

def write_file(name, content):
    try:
        os.makedirs(os.path.dirname(name) if "/" in name else ".", exist_ok=True)
        with open(name, "w") as f:
            f.write(content)
        return f"Written: {name}"
    except Exception as e:
        return f"Error writing file: {e}"

def deploy_worker(name, code):
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        return "Missing CF_API_TOKEN or CF_ACCOUNT_ID env vars"
    try:
        r = requests.put(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/workers/scripts/{name}",
            headers={
                "Authorization": f"Bearer {CF_API_TOKEN}",
                "Content-Type": "application/javascript"
            },
            data=code
        )
        data = r.json()
        if data.get("success"):
            return f"Deployed! https://{name}.{CF_ACCOUNT_ID}.workers.dev"
        return f"Failed: {data.get('errors')}"
    except Exception as e:
        return f"Deploy error: {e}"

def process_actions(text):
    results = []

    # Handle <RUN> blocks
    for match in re.finditer(r'<RUN>(.*?)</RUN>', text, re.DOTALL):
        cmd = match.group(1).strip()
        out = run_command(cmd)
        results.append(f"$ {cmd}\n{out}")

    # Handle <FILE> blocks
    for match in re.finditer(r'<FILE name="([^"]+)">(.*?)</FILE>', text, re.DOTALL):
        name, content = match.group(1), match.group(2).strip()
        out = write_file(name, content)
        results.append(out)

    # Handle <DEPLOY> blocks
    for match in re.finditer(r'<DEPLOY name="([^"]+)">(.*?)</DEPLOY>', text, re.DOTALL):
        name, code = match.group(1), match.group(2).strip()
        out = deploy_worker(name, code)
        results.append(out)

    return "\n\n".join(results) if results else None

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    msg = update.message.text

    if uid not in history:
        history[uid] = []
    history[uid].append({"role": "user", "content": msg})

    # Keep last 20 messages
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

        # Execute any actions in the reply
        action_output = process_actions(reply)

        # Send reply (split if too long)
        chunks = [reply[i:i+4000] for i in range(0, len(reply), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk)

        # Send action results
        if action_output:
            await update.message.reply_text(f"📟 Output:\n{action_output}")

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def start(update, ctx):
    await update.message.reply_text(
        "🦆 Goose Agent ready\n\n"
        "I can:\n"
        "• Run code on the server\n"
        "• Build & deploy Cloudflare Workers\n"
        "• Write files\n"
        "• Reason through problems\n\n"
        "Just tell me what to build."
    )

async def clear(update, ctx):
    history.pop(update.message.chat_id, None)
    await update.message.reply_text("Memory cleared.")

async def run(update, ctx):
    cmd = " ".join(ctx.args)
    if cmd:
        out = run_command(cmd)
        await update.message.reply_text(f"$ {cmd}\n{out}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("clear", clear))
app.add_handler(CommandHandler("run", run))
app.add_handler(MessageHandler(filters.TEXT, handle))

if RENDER_URL:
    
else:
    app.run_polling(drop_pending_updates=True)
app.run_webhook(listen="0.0.0.0", port=PORT, url_path="/webhook", webhook_url=f"{RENDER_URL}/webhook")
