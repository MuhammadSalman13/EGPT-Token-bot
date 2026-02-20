# egpt_full_bot_ready_supabase.py
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

# -------- قائمة الترحيب ----------
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
        c.execute("UPDATE users SET micro_tokens=%s, last_checkin=%s WHERE user_id=%s", (micro_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(f"Daily Check-in done! You earned {MICRO_TOKENS_CHECKIN} Micro-Tokens.\nTotal: {micro_tokens}", reply_markup=WELCOME_KEYBOARD)

    elif text == "💳 Set Wallet":
        await update.message.reply_text("Please send me your USDT wallet address on BSC network now:", reply_markup=WELCOME_KEYBOARD)

    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text(f"Minimum withdraw is {WITHDRAW_MIN_EGPT} EGPT. Your balance: {egpt_balance:.2f} EGPT", reply_markup=WELCOME_KEYBOARD)
            return
        if invited_count < INVITE_REQUIREMENT:
            await update.message.reply_text(f"You need at least {INVITE_REQUIREMENT} invited friends to withdraw.\nCurrent: {invited_count}", reply_markup=WELCOME_KEYBOARD)
            return
        if not wallet_address:
            await update.message.reply_text("Please set your wallet first using 'Set Wallet'.", reply_markup=WELCOME_KEYBOARD)
            return
        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (%s,%s,%s,%s)",
                  (user_id, egpt_balance, wallet_address, now))
        conn.commit()
        await update.message.reply_text(f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval by admin.", reply_markup=WELCOME_KEYBOARD)

    # -------- استقبال Wallet Address --------
    elif text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=%s WHERE user_id=%s", (text, user_id))
        conn.commit()
        await update.message.reply_text("Wallet address saved successfully!", reply_markup=WELCOME_KEYBOARD)

    else:
        await update.message.reply_text("Invalid input. Use the buttons below.", reply_markup=WELCOME_KEYBOARD)

# -------- أوامر Admin ----------
async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    c.execute("SELECT id, user_id, amount_egpt, wallet_address, request_date FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("No pending withdrawals.", reply_markup=WELCOME_KEYBOARD)
        return
    msg = "Pending Withdrawals:\n"
    for r in rows:
        msg += f"ID: {r[0]}, User: {r[1]}, Amount: {r[2]:.2f} EGPT, Wallet: {r[3]}, Date: {r[4]}\n"
    await update.message.reply_text(msg, reply_markup=WELCOME_KEYBOARD)

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <withdraw_id>", reply_markup=WELCOME_KEYBOARD)
        return
    withdraw_id = args[0]
    c.execute("SELECT user_id, amount_egpt FROM withdrawals WHERE id=%s AND status='pending'", (withdraw_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("Withdraw request not found.", reply_markup=WELCOME_KEYBOARD)
        return
    uid, amount = row
    micro_deduction = amount * (MICRO_TOKENS_TO_EGPT / 10)
    c.execute("SELECT micro_tokens FROM users WHERE user_id=%s", (uid,))
    user_micro = c.fetchone()[0]
    new_micro = max(0, user_micro - micro_deduction)
    c.execute("UPDATE users SET micro_tokens=%s WHERE user_id=%s", (new_micro, uid))
    c.execute("UPDATE withdrawals SET status='approved' WHERE id=%s", (withdraw_id,))
    conn.commit()
    await update.message.reply_text(f"Withdrawal {withdraw_id} approved. User {uid} balance updated.", reply_markup=WELCOME_KEYBOARD)

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /reject <withdraw_id>", reply_markup=WELCOME_KEYBOARD)
        return
    withdraw_id = args[0]
    c.execute("UPDATE withdrawals SET status='rejected' WHERE id=%s AND status='pending'", (withdraw_id,))
    conn.commit()
    await update.message.reply_text(f"Withdrawal {withdraw_id} rejected.", reply_markup=WELCOME_KEYBOARD)

# -------- تشغيل البوت ----------
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
