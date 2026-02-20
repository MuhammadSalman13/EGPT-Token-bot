import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# قراءة المتغيرات من Environment
DATABASE_URL = os.environ.get("DATABASE_URL")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not DATABASE_URL or not BOT_TOKEN:
    raise Exception("Environment variables DATABASE_URL or BOT_TOKEN not set!")

# الاتصال بقاعدة البيانات
try:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    print("✅ Database connected successfully!")
except Exception as e:
    print("❌ Database connection failed:", e)
    exit(1)

# إنشاء جدول todos إذا لم يكن موجود
cursor.execute("""
CREATE TABLE IF NOT EXISTS todos (
    id SERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    done BOOLEAN DEFAULT FALSE
);
""")
conn.commit()
print("✅ Table 'todos' ready!")

# إعداد البوت باستخدام ApplicationBuilder (v20+)
app = ApplicationBuilder().token(BOT_TOKEN).build()

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بوت EGPT شغال!")

async def add_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if not task:
        await update.message.reply_text("اكتب المهمة بعد الأمر!")
        return
    cursor.execute("INSERT INTO todos (task) VALUES (%s) RETURNING id;", (task,))
    conn.commit()
    await update.message.reply_text(f"تم إضافة المهمة: {task}")

async def list_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT id, task, done FROM todos ORDER BY id;")
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("لا توجد مهام بعد!")
        return
    message = "\n".join([f"{row['id']}. [{'✅' if row['done'] else '❌'}] {row['task']}" for row in rows])
    await update.message.reply_text(message)

# تسجيل الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_todo))
app.add_handler(CommandHandler("list", list_todos))

# تشغيل البوت
print("🚀 Bot is starting...")
app.run_polling()
