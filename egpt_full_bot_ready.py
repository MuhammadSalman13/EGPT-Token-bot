import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime

conn = sqlite3.connect('egpt_bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, micro_tokens INTEGER DEFAULT 0, last_tap TEXT, last_checkin TEXT, invited_count INTEGER DEFAULT 0, wallet_address TEXT DEFAULT NULL)')
c.execute('CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount_egpt REAL, wallet_address TEXT, status TEXT DEFAULT "pending", request_date TEXT)')
conn.commit()

MICRO_TOKENS_PER_TAP = 10000
MICRO_TOKENS_DAILY_MAX = 500000
MICRO_TOKENS_CHECKIN = 50000
MICRO_TOKENS_INVITE = 100000
MICRO_TOKENS_TO_EGPT = 1000000
WITHDRAW_MIN_EGPT = 100
INVITE_REQUIREMENT = 10
ADMIN_IDS = [5808513261]
BOT_USERNAME = "EGPTCOINSBot"

WELCOME_KEYBOARD = ReplyKeyboardMarkup([
    ["💰 Earn", "📊 Balance"],
    ["👥 Referrals", "🎁 Daily Check-in"],
    ["💳 Set Wallet", "💸 Withdraw"]
], resize_keyboard=True, one_time_keyboard=False)

WELCOME_MESSAGE = "Welcome to EGPT Bot! Use buttons below."

ADMIN_IDS = [5808513261]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=WELCOME_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    micro_tokens = 0
    last_tap = None
    last_checkin = None
    invited_count = 0
    wallet_address = None
    
    if row:
        micro_tokens = row[0]
        last_tap = row[1]
        last_checkin = row[2]
        invited_count = row[3]
        wallet_address = row[4]
    
    now = datetime.now().strftime("%Y-%m-%d")

    if user_id in ADMIN_IDS and text == "/admin":
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        c.execute("SELECT SUM(micro_tokens) FROM users")
        total_balance = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        pending_count = c.fetchone()[0]
        
        admin_msg = "ADMIN PANEL
"
        admin_msg += "Users: " + str(users_count) + "
"
        admin_msg += "Total Balance: " + str(total_balance) + "
"
        admin_msg += "Pending Withdrawals: " + str(pending_count)
        
        await update.message.reply_text(admin_msg, reply_markup=WELCOME_KEYBOARD)
        return

    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=?, last_tap=? WHERE user_id=?", (daily_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text("You earned 10000 Micro-Tokens! Total today: " + str(daily_tokens), reply_markup=WELCOME_KEYBOARD)

    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"
        balance_msg = "Your Balance:
"
        balance_msg += "Micro-Tokens: " + str(micro_tokens) + "
"
        balance_msg += "EGPT: " + str(egpt)[:5] + "
"
        balance_msg += "Invited Friends: " + str(invited_count) + "
"
        balance_msg += "Wallet: " + wallet_info
        await update.message.reply_text(balance_msg, reply_markup=WELCOME_KEYBOARD)

    elif text == "👥 Referrals":
        invite_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(user_id)
        await update.message.reply_text("Share this link:
" + invite_link, reply_markup=WELCOME_KEYBOARD)

    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text("You already did your daily check-in today!", reply_markup=WELCOME_KEYBOARD)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=?, last_checkin=? WHERE user_id=?", (micro_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text("Daily Check-in done! You earned 50000 Micro-Tokens.", reply_markup=WELCOME_KEYBOARD)

    elif text == "💳 Set Wallet":
        await update.message.reply_text("Please send me your USDT wallet address on BSC network now:", reply_markup=WELCOME_KEYBOARD)

    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text("Minimum withdraw is 100 EGPT. Your balance: " + str(egpt_balance)[:5] + " EGPT", reply_markup=WELCOME_KEYBOARD)
            return
        if not wallet_address:
            await update.message.reply_text("Please set your wallet first using 'Set Wallet'.", reply_markup=WELCOME_KEYBOARD)
            return
        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (?,?,?,?)", (user_id, egpt_balance, wallet_address, now))
        conn.commit()
        await update.message.reply_text("Your withdraw request has been submitted and is pending approval by admin.", reply_markup=WELCOME_KEYBOARD)

    elif text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=? WHERE user_id=?", (text, user_id))
        conn.commit()
        await update.message.reply_text("Wallet address saved successfully!", reply_markup=WELCOME_KEYBOARD)

    else:
        await update.message.reply_text("Invalid input. Use the buttons below.", reply_markup=WELCOME_KEYBOARD)

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    c.execute("SELECT id, user_id, amount_egpt, wallet_address FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("No pending withdrawals.")
        return
    msg = "Pending Withdrawals:
"
    for r in rows:
        msg += "ID: " + str(r[0]) + ", User: " + str(r[1]) + ", Amount: " + str(r[2])[:5] + " EGPT
"
    await update.message.reply_text(msg)

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <withdraw_id>")
        return
    withdraw_id = args[0]
    c.execute("UPDATE withdrawals SET status='approved' WHERE id=? AND status='pending'", (withdraw_id,))
    conn.commit()
    await update.message.reply_text("Withdrawal " + str(withdraw_id) + " approved.")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not 
