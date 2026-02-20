# egpt_full_bot_ready.py
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime

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

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Stats", "💰 Total Balance"],
        ["💸 Pending", "🔙 Back"]
    ], resize_keyboard=True)

WELCOME_MESSAGE = "مرحبًا بك في EGPT Bot!
استخدم الأزرار أدناه للوصول لجميع المزايا."

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
    micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row if row else (0, None, None, 0, None)
    now = datetime.now().strftime("%Y-%m-%d")

    if user_id in ADMIN_IDS and text == "/admin":
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT SUM(micro_tokens) FROM users")
        total_balance = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        pending = c.fetchone()[0]
        await update.message.reply_text(
            f"🔧 لوحة الأدمن:
"
            f"👥 المستخدمين: {total_users}
"
            f"💰 الرصيد الكلي: {total_balance:,}
"
            f"💸 طلبات معلقة: {pending}",
            reply_markup=get_admin_keyboard()
        )
        return

    if user_id in ADMIN_IDS and text == "📊 Stats":
        c.execute("SELECT user_id, micro_tokens FROM users ORDER BY micro_tokens DESC LIMIT 5")
        top = c.fetchall()
        msg = "🏆 أعلى 5 رصيد:
"
        for user in top:
            egpt = user[1] / MICRO_TOKENS_TO_EGPT * 10
            msg += f"ID {user[0]}: {user[1]:,} ({egpt:.1f} EGPT)
"
        await update.message.reply_text(msg, reply_markup=get_admin_keyboard())
        return

    if user_id in ADMIN_IDS and text == "💰 Total Balance":
        c.execute("SELECT SUM(micro_tokens) FROM users")
        total = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM users WHERE micro_tokens > 0")
        active = c.fetchone()[0]
        await update.message.reply_text(
            f"💰 إجمالي الرصيد: {total:,} Micro
"
            f"👥 مستخدمين نشطين: {active}",
            reply_markup=get_admin_keyboard()
        )
        return

    if user_id in ADMIN_IDS and text == "💸 Pending":
        c.execute("SELECT id, user_id, amount_egpt, wallet_address FROM withdrawals WHERE status='pending'")
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("لا توجد طلبات معلقة", reply_markup=WELCOME_KEYBOARD)
            return
        msg = "💸 الطلبات المعلقة:
"
        for r in rows:
            msg += f"ID {r[0]} | User {r[1]} | {r[2]:.1f} EGPT
Wallet: {r[3][:10]}...
"
        await update.message.reply_text(msg, reply_markup=WELCOME_KEYBOARD)
        return

    if user_id in ADMIN_IDS and text == "🔙 Back":
        await update.message.reply_text("🔙 العودة للقائمة الرئيسية", reply_markup=WELCOME_KEYBOARD)
        return

    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=?, last_tap=? WHERE user_id=?", (daily_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(f"You earned {MICRO_TOKENS_PER_TAP} Micro-Tokens! Total today: {daily_tokens}", reply_markup=WELCOME_KEYBOARD)

    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"
        await update.message.reply_text(
            f"Your Balance:
Micro-Tokens: {micro_tokens}
EGPT: {egpt:.2f}
Invited Friends: {invited_count}
Wallet: {wallet_info}",
            reply_markup=WELCOME_KEYBOARD
        )

    elif text == "👥 Referrals":
        invite_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(
            f"Share this link to invite friends and earn {MICRO_TOKENS_INVITE} Micro-Tokens each:
{invite_link}",
            reply_markup=WELCOME_KEYBOARD
        )

    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text("You already did your daily check-in today!", reply_markup=WELCOME_KEYBOARD)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=?, last_checkin=? WHERE user_id=?", (micro_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(
            f"Daily Check-in done! You earned {MICRO_TOKENS_CHECKIN} Micro-Tokens.
Total: {micro_tokens}",
            reply_markup=WELCOME_KEYBOARD
        )

    elif text == "💳 Set Wallet":
        await update.message.reply_text("Please send me your USDT wallet address on BSC network now:", reply_markup=WELCOME_KEYBOARD)

    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text(f"Minimum withdraw is {WITHDRAW_MIN_EGPT} EGPT. Your balance: {egpt_balance:.2f} EGPT", reply_markup=WELCOME_KEYBOARD)
            return
        if invited_count < INVITE_REQUIREMENT:
            await update.message.reply_text(f"You need at least {INVITE_REQUIREMENT} invited friends to withdraw.
Current: {invited_count}", reply_markup=WELCOME_KEYBOARD)
            return
        if not wallet_address:
            await update.message.reply_text("Please set your wallet first using 'Set Wallet'.", reply_markup=WELCOME_KEYBOARD)
            return
        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (?,?,?,?)",
                  (user_id, egpt_balance, wallet_address, now))
        conn.commit()
        await update.message.reply_text(f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval by admin.", reply_markup=WELCOME_KEYBOARD)

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
    c.execute("SELECT id, user_id, amount_egpt, wallet_address, request_date FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("No pending withdrawals.", reply_markup=WELCOME_KEYBOARD)
        return
    msg = "Pending Withdrawals:
"
    for r in rows:
        msg += f"ID: {r[0]}, User: {r[1]}, Amount: {r[2]:.2f} EGPT, Wallet: {r[3]}, Date: {r[4]}
"
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
    c.execute("SELECT user_id, amount_egpt FROM withdrawals WHERE id=? AND status='pending'", (withdraw_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("Withdraw request not found.", reply_markup=WELCOME_KEYBOARD)
        return
    uid, amount = row
    micro_deduction = amount * (MICRO_TOKENS_TO_EGPT / 10)
    c.execute("SELECT micro_tokens FROM users WHERE user_id=?", (uid,))
    user_micro = c.fetchone()[0]
    new_micro = max(0, user_micro - micro_deduction)
    c.execute("UPDATE users SET micro_tokens=? WHERE user_id=?", (new_micro, uid))
    c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (withdraw_id,))
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
    c.execute("UPDATE withdrawals SET status='rejected' WHERE id=? AND status='pending'", (withdraw_id,))
    conn.commit()
    await update.message.reply_text(f"Withdrawal {withdraw_id} rejected.", reply_markup=WELCOME_KEYBOARD)

def main():
    TOKEN = "8594208349:AAF8BqZUWs9TCOqo3Lw7Jw3kxva7BBKruX4"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
