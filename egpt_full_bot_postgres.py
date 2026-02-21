import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime

# -------- الاتصال بقاعدة البيانات ----------
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
c = conn.cursor()

# -------- إنشاء الجداول ----------
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id BIGINT PRIMARY KEY,
    micro_tokens BIGINT DEFAULT 0,
    last_tap TEXT,
    last_checkin TEXT,
    invited_count INTEGER DEFAULT 0,
    wallet_address TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS withdrawals(
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    amount_egpt REAL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    request_date TEXT
)
""")

# -------- إعدادات البوت ----------
MICRO_TOKENS_PER_TAP = 10000
MICRO_TOKENS_DAILY_MAX = 500000
MICRO_TOKENS_CHECKIN = 50000
MICRO_TOKENS_INVITE = 100000
MICRO_TOKENS_TO_EGPT = 1000000
WITHDRAW_MIN_EGPT = 100
INVITE_REQUIREMENT = 10
ADMIN_IDS = [123456789]
BOT_USERNAME = "EGPTCOINSBot"

WELCOME_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💰 Earn", "📊 Balance"],
        ["👥 Referrals", "🎁 Daily Check-in"],
        ["💳 Set Wallet", "💸 Withdraw"]
    ],
    resize_keyboard=True
)

WELCOME_MESSAGE = "مرحبًا بك في EGPT Bot!\nاستخدم الأزرار أدناه للوصول لجميع المزايا."

# -------- بدء البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=WELCOME_KEYBOARD)

# -------- التعامل مع الرسائل ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    c.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=%s", (user_id,))
    row = c.fetchone()

    micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
    now = datetime.now().strftime("%Y-%m-%d")

    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=%s, last_tap=%s WHERE user_id=%s",
                  (daily_tokens, now, user_id))
        await update.message.reply_text(
            f"You earned {MICRO_TOKENS_PER_TAP} Micro-Tokens! Total today: {daily_tokens}",
            reply_markup=WELCOME_KEYBOARD)

    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"
        await update.message.reply_text(
            f"Your Balance:\nMicro-Tokens: {micro_tokens}\nEGPT: {egpt:.2f}\nInvited Friends: {invited_count}\nWallet: {wallet_info}",
            reply_markup=WELCOME_KEYBOARD)

    elif text == "👥 Referrals":
        invite_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(
            f"Share this link to invite friends and earn {MICRO_TOKENS_INVITE} Micro-Tokens each:\n{invite_link}",
            reply_markup=WELCOME_KEYBOARD)

    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text("You already did your daily check-in today!",
                                            reply_markup=WELCOME_KEYBOARD)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=%s, last_checkin=%s WHERE user_id=%s",
                  (micro_tokens, now, user_id))
        await update.message.reply_text(
            f"Daily Check-in done! You earned {MICRO_TOKENS_CHECKIN} Micro-Tokens.\nTotal: {micro_tokens}",
            reply_markup=WELCOME_KEYBOARD)

    elif text == "💳 Set Wallet":
        await update.message.reply_text(
            "Please send me your USDT wallet address on BSC network now:",
            reply_markup=WELCOME_KEYBOARD)

    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text(
                f"Minimum withdraw is {WITHDRAW_MIN_EGPT} EGPT. Your balance: {egpt_balance:.2f} EGPT",
                reply_markup=WELCOME_KEYBOARD)
            return
        if invited_count < INVITE_REQUIREMENT:
            await update.message.reply_text(
                f"You need at least {INVITE_REQUIREMENT} invited friends to withdraw.\nCurrent: {invited_count}",
                reply_markup=WELCOME_KEYBOARD)
            return
        if not wallet_address:
            await update.message.reply_text(
                "Please set your wallet first using 'Set Wallet'.",
                reply_markup=WELCOME_KEYBOARD)
            return

        c.execute("""INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date)
                     VALUES (%s, %s, %s, %s)""",
                  (user_id, egpt_balance, wallet_address, now))

        await update.message.reply_text(
            f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval by admin.",
            reply_markup=WELCOME_KEYBOARD)

    elif text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=%s WHERE user_id=%s",
                  (text, user_id))
        await update.message.reply_text("Wallet address saved successfully!",
                                        reply_markup=WELCOME_KEYBOARD)

    else:
        await update.message.reply_text("Invalid input. Use the buttons below.",
                                        reply_markup=WELCOME_KEYBOARD)

# -------- تشغيل البوت ----------
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
