# egpt_full_bot_ready.py
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime

# -------- قاعدة البيانات ----------
conn = sqlite3.connect('egpt_bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    micro_tokens INTEGER DEFAULT 0,
    last_tap TEXT,
    last_checkin TEXT,
    invited_count INTEGER DEFAULT 0,
    wallet_address TEXT DEFAULT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS withdrawals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount_egpt REAL,
    wallet_address TEXT,
    status TEXT DEFAULT 'pending',
    request_date TEXT
)
''')
conn.commit()

# -------- إعدادات ----------
MICRO_TOKENS_PER_TAP = 10000
MICRO_TOKENS_DAILY_MAX = 500000
MICRO_TOKENS_CHECKIN = 50000
MICRO_TOKENS_INVITE = 100000
MICRO_TOKENS_TO_EGPT = 1000000
WITHDRAW_MIN_EGPT = 100
INVITE_REQUIREMENT = 10
ADMIN_IDS = [5808513261]   # ✅ انت الأدمن
BOT_USERNAME = "EGPTCOINSBot"

# -------- لوحة المفاتيح الديناميكية ----------
def get_keyboard(user_id):
    keyboard = [
        ["💰 Earn", "📊 Balance"],
        ["👥 Referrals", "🎁 Daily Check-in"],
        ["💳 Set Wallet", "💸 Withdraw"]
    ]

    if user_id in ADMIN_IDS:
        keyboard.append(["🛠 Admin Panel"])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

WELCOME_MESSAGE = "مرحبًا بك في EGPT Bot!\nاستخدم الأزرار أدناه للوصول لجميع المزايا."

# -------- Start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()

    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=get_keyboard(user_id)
    )

# -------- Handle Messages ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()

    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
    now = datetime.now().strftime("%Y-%m-%d")

    # Earn
    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX

        c.execute("UPDATE users SET micro_tokens=?, last_tap=? WHERE user_id=?", (daily_tokens, now, user_id))
        conn.commit()

        await update.message.reply_text(
            f"You earned {MICRO_TOKENS_PER_TAP} Micro-Tokens! Total today: {daily_tokens}",
            reply_markup=get_keyboard(user_id)
        )

    # Balance
    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"

        await update.message.reply_text(
            f"Your Balance:\nMicro-Tokens: {micro_tokens}\nEGPT: {egpt:.2f}\nInvited Friends: {invited_count}\nWallet: {wallet_info}",
            reply_markup=get_keyboard(user_id)
        )

    # Referrals
    elif text == "👥 Referrals":
        invite_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(
            f"Share this link to invite friends and earn {MICRO_TOKENS_INVITE} Micro-Tokens each:\n{invite_link}",
            reply_markup=get_keyboard(user_id)
        )

    # Check-in
    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text(
                "You already did your daily check-in today!",
                reply_markup=get_keyboard(user_id)
            )
            return

        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=?, last_checkin=? WHERE user_id=?", (micro_tokens, now, user_id))
        conn.commit()

        await update.message.reply_text(
            f"Daily Check-in done! You earned {MICRO_TOKENS_CHECKIN} Micro-Tokens.\nTotal: {micro_tokens}",
            reply_markup=get_keyboard(user_id)
        )

    # Set Wallet
    elif text == "💳 Set Wallet":
        await update.message.reply_text(
            "Please send me your USDT wallet address on BSC network now:",
            reply_markup=get_keyboard(user_id)
        )

    # Withdraw
    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10

        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text(
                f"Minimum withdraw is {WITHDRAW_MIN_EGPT} EGPT. Your balance: {egpt_balance:.2f} EGPT",
                reply_markup=get_keyboard(user_id)
            )
            return

        if invited_count < INVITE_REQUIREMENT:
            await update.message.reply_text(
                f"You need at least {INVITE_REQUIREMENT} invited friends to withdraw.\nCurrent: {invited_count}",
                reply_markup=get_keyboard(user_id)
            )
            return

        if not wallet_address:
            await update.message.reply_text(
                "Please set your wallet first using 'Set Wallet'.",
                reply_markup=get_keyboard(user_id)
            )
            return

        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (?,?,?,?)",
                  (user_id, egpt_balance, wallet_address, now))
        conn.commit()

        await update.message.reply_text(
            f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval.",
            reply_markup=get_keyboard(user_id)
        )

    # Admin Panel
    elif text == "🛠 Admin Panel" and user_id in ADMIN_IDS:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        pending = c.fetchone()[0]

        await update.message.reply_text(
            f"🛠 Admin Panel\n\n👥 Total Users: {total_users}\n💸 Pending Withdrawals: {pending}\n\nUse:\n/pending\n/approve <id>\n/reject <id>",
            reply_markup=get_keyboard(user_id)
        )

    # Wallet address input
    elif text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=? WHERE user_id=?", (text, user_id))
        conn.commit()

        await update.message.reply_text(
            "Wallet address saved successfully!",
            reply_markup=get_keyboard(user_id)
        )

    else:
        await update.message.reply_text(
            "Invalid input. Use the buttons below.",
            reply_markup=get_keyboard(user_id)
        )

# -------- تشغيل ----------
def main():
    TOKEN = "YOUR_TOKEN_HERE"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
