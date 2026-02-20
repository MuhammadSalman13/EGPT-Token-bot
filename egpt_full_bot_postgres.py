import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# =====================================
# DATABASE SETUP
# =====================================
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable is not set!")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("❌ Database connection failed:", e)
        return None

def setup_database():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Table 'todos' is ready")

# =====================================
# BOT SETUP
# =====================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable is not set!")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Hello! I am your EGPT Bot. ✅")

def add_todo(update: Update, context: CallbackContext):
    conn = get_db_connection()
    if not conn:
        update.message.reply_text("❌ Database not available")
        return

    todo_text = " ".join(context.args)
    if not todo_text:
        update.message.reply_text("Usage: /add <todo_text>")
        return

    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (title) VALUES (%s)", (todo_text,))
    conn.commit()
    cursor.close()
    conn.close()
    update.message.reply_text(f"✅ Added todo: {todo_text}")

def list_todos(update: Update, context: CallbackContext):
    conn = get_db_connection()
    if not conn:
        update.message.reply_text("❌ Database not available")
        return

    cursor = conn.cursor()
    cursor.execute("SELECT id, title, completed FROM todos ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        update.message.reply_text("No todos found.")
        return

    message = "\n".join([f"{row['id']}. {row['title']} - {'✅' if row['completed'] else '❌'}" for row in rows])
    update.message.reply_text(message)

def main():
    setup_database()
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_todo))
    dp.add_handler(CommandHandler("list", list_todos))

    print("🤖 Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
