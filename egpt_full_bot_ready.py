# egpt_full_bot_ready_v2.py
import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime

# -------- إعدادات البوت ----------
MICRO_TOKENS_PER_TAP = 10000
MICRO_TOKENS_DAILY_MAX = 500000
MICRO_TOKENS_CHECKIN = 50000
MICRO_TOKENS_INVITE = 100000
MICRO_TOKENS_TO_EGPT = 1000000  # 1,000,000 Micro = 10 EGPT
WITHDRAW_MIN_EGPT = 100
INVITE_REQUIREMENT = 10
ADMIN_IDS = [123456789]  # ضع Telegram ID الخاص بك
BOT_USERNAME = "EGPTCOINSBot"  # اسم البوت بدون @

# -------- قائمة الترحيب الثابتة تحت خانة الكتابة ----------
WELCOME_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💰 Earn", "📊 Balance"],
        ["👥 Referrals", "🎁 Daily Check-in"],
        ["💳 Set Wallet", "💸 Withdraw"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

WELCOME_MESSAGE = "مرحبًا بك في EGPT Bot!\nاستخدم الأزرار أدناه للوصول لجميع المزايا."

# -------- الاتصال بقاعدة البيانات عبر Supabase ----------
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
c = conn.cursor()

# -------- إنشاء الجداول لو مش موجودة ----------
c.execute('''
CREATE TABLE IF NOT EXISTS users(
    user_id BIGINT PRIMARY KEY,
    micro_tokens BIGINT DEFAULT 0,
    last_tap TEXT,
    last_checkin TEXT,
    invited_count INT DEFAULT 0,
    wallet_address TEXT DEFAULT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS withdrawals(
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    amount_egpt REAL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    request_date TEXT
)
''')
conn.commit()

# -------- بدء البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT(user_id) DO NOTHING", (user_id,))
    conn.commit()
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=WELCOME_KEYBOARD)

# -------- التعامل مع الرسائل --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    c.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT(user_id) DO NOTHING", (user_id,))
    conn.commit()
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
    now = datetime.now().strftime("%Y-%m-%d")

    # -------- وظائف الأزرار --------
    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=%s, last_tap=%s WHERE user_id=%s", (daily_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(f"You earned {MICRO_TOKENS_PER_TAP} Micro-Tokens! Total today: {daily_tokens}", reply_markup=WELCOME_KEYBOARD)

    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"
        await update.message.reply_text(f"Your Balance:\nMicro-Tokens: {micro_tokens}\nEGPT: {egpt:.2f}\nInvited Friends: {invited_count}\nWallet: {wallet_info}", reply_markup=WELCOME_KEYBOARD)

    elif text == "👥 Referrals":
        invite_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(f"Share this link to invite friends and earn {MICRO_TOKENS_INVITE} Micro-Tokens each:\n{invite_link}", reply_markup=WELCOME_KEYBOARD)

    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text("You already did your daily check-in today!", reply_markup=WELCOME_KEYBOARD)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=%s, last_checkin=%s WHERE user_id=%s", (
