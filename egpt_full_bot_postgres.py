import os
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === إعدادات البوت ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # ضع توكن البوت في Environment Variables
DATABASE_URL = os.environ.get("DATABASE_URL")  # الرابط اللي حضرتك حطّيته

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN not found in environment variables!")

if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL not found in environment variables!")

# === الاتصال بقاعدة البيانات ===
try:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    print("✅ Database connection successful!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    raise e

# === التأكد من وجود جدول todos ===
try:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS todos (
        id BIGSERIAL PRIMARY KEY,
        task TEXT NOT NULL,
        status TEXT DEFAULT 'Not Started',
        inserted_at TIMESTAMP DEFAULT NOW()
    );
    """)
    conn.commit()
    print("✅ Table 'todos' is ready!")
except Exception as e:
    print(f"❌ Failed to create/check table: {e}")
    raise e

# === أوامر البوت ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! البوت شغال 🚀")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ استخدم: /add <وصف المهمة>")
        return
    task_text = " ".join(context.args)
    try:
        cursor.execute(
            "INSERT INTO todos (task, status, inserted_at) VALUES (%s, %s, NOW())",
            (task_text, "Not Started")
        )
        conn.commit()
        await update.message.reply_text(f"✅ تمت إضافة المهمة: {task_text}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ أثناء إضافة المهمة: {e}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute("SELECT id, task, status FROM todos ORDER BY inserted_at DESC")
        rows = cursor.fetchall()
        if not rows:
            await update.message.reply_text("لا توجد مهام حالياً.")
            return
        msg = "\n".join([f"{row['id']}. {row['task']} - {row['status']}" for row in rows])
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ أثناء جلب المهام: {e}")

# === تشغيل البوت ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("list", list_tasks))
    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
