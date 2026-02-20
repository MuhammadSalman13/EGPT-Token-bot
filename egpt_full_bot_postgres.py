import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Bot
from telegram.ext import Updater, CommandHandler

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

# إعداد بوت التليجرام
bot = Bot(token=BOT_TOKEN)
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# أوامر بسيطة
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="بوت EGPT شغال!")

def add_todo(update, context):
    task = " ".join(context.args)
    if not task:
        context.bot.send_message(chat_id=update.effective_chat.id, text="اكتب المهمة بعد الأمر!")
        return
    cursor.execute("INSERT INTO todos (task) VALUES (%s) RETURNING id;", (task,))
    conn.commit()
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"تم إضافة المهمة: {task}")

def list_todos(update, context):
    cursor.execute("SELECT id, task, done FROM todos ORDER BY id;")
    rows = cursor.fetchall()
    if not rows:
        context.bot.send_message(chat_id=update.effective_chat.id, text="لا توجد مهام بعد!")
        return
    message = "\n".join([f"{row['id']}. [{'✅' if row['done'] else '❌'}] {row['task']}" for row in rows])
    context.bot.send_message(chat_id=update.effective_chat.id, text=message)

# تسجيل الأوامر
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("add", add_todo))
dispatcher.add_handler(CommandHandler("list", list_todos))

# تشغيل البوت
print("🚀 Bot is starting...")
updater.start_polling()
updater.idle()
