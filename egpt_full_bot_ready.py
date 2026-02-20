# egpt_full_bot_ready_v2.py
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import datetime

# -------- قاعدة البيانات ----------
conn = sqlite3.connect('egpt_bot.db', check_same_thread=False)
c = conn.cursor()

# جدول المستخدمين
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

# جدول طلبات السحب
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

# -------- القائمة الجديدة (ثابتة) --------
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Tap to Earn", callback_data='tap')],
        [InlineKeyboardButton("📊 Check Balance", callback_data='balance')],
        [InlineKeyboardButton("👥 Invite Friend", callback_data='invite')],
        [InlineKeyboardButton("🎁 Daily Check-in", callback_data='checkin')],
        [InlineKeyboardButton("💳 Set Wallet", callback_data='set_wallet')],
        [InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------- أوامر البوت --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text(
        "Welcome to EGPT Era Bot!\nCollect Micro-Tokens and convert them to EGPT.",
        reply_markup=main_keyboard()
    )

# -------- التعامل مع أزرار Inline ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row

    # استخدام القائمة الجديدة مع كل رسالة
    reply_markup = main_keyboard()

    if query.data == 'tap':
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=?, last_tap=? WHERE user_id=?", (daily_tokens, now, user_id))
        conn.commit()
        await query.edit_message_text(
            f"You earned {MICRO_TOKENS_PER_TAP} Micro-Tokens! Total today: {daily_tokens}",
            reply_markup=reply_markup
        )

    elif query.data == 'balance':
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address if wallet_address else "Not Set"
        await query.edit_message_text(
            f"Your Balance:\nMicro-Tokens: {micro_tokens}\nEGPT: {egpt:.2f}\nInvited Friends: {invited_count}\nWallet: {wallet_info}",
            reply_markup=reply_markup
        )

    elif query.data == 'invite':
        invite_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await query.edit_message_text(
            f"Share this link to invite friends and earn {MICRO_TOKENS_INVITE} Micro-Tokens each:\n{invite_link}",
            reply_markup=reply_markup
        )

    elif query.data == 'checkin':
        if last_checkin == now:
            await query.edit_message_text("You already did your daily check-in today!", reply_markup=reply_markup)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=?, last_checkin=? WHERE user_id=?", (micro_tokens, now, user_id))
        conn.commit()
        await query.edit_message_text(
            f"Daily Check-in done! You earned {MICRO_TOKENS_CHECKIN} Micro-Tokens.\nTotal: {micro_tokens}",
            reply_markup=reply_markup
        )

    elif query.data == 'set_wallet':
        await query.edit_message_text("Please send me your USDT wallet address on BSC network now:", reply_markup=reply_markup)

    elif query.data == 'withdraw':
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await query.edit_message_text(f"Minimum withdraw is {WITHDRAW_MIN_EGPT} EGPT. Your balance: {egpt_balance:.2f} EGPT", reply_markup=reply_markup)
            return
        if invited_count < INVITE_REQUIREMENT:
            await query.edit_message_text(f"You need at least {INVITE_REQUIREMENT} invited friends to withdraw.\nCurrent: {invited_count}", reply_markup=reply_markup)
            return
        if not wallet_address:
            await query.edit_message_text("Please set your wallet first using 'Set Wallet'.", reply_markup=reply_markup)
            return
        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (?,?,?,?)",
                  (user_id, egpt_balance, wallet_address, now))
        conn.commit()
        await query.edit_message_text(f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval by admin.", reply_markup=reply_markup)

# -------- استقبال Wallet Address من المستخدم --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    if text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=? WHERE user_id=?", (text, user_id))
        conn.commit()
        await update.message.reply_text("Wallet address saved successfully!", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("Invalid wallet address. Make sure it starts with 0x and is 42 characters long.", reply_markup=main_keyboard())

# -------- أوامر Admin ----------
async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    c.execute("SELECT id, user_id, amount_egpt, wallet_address, request_date FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("No pending withdrawals.", reply_markup=main_keyboard())
        return
    msg = "Pending Withdrawals:\n"
    for r in rows:
        msg += f"ID: {r[0]}, User: {r[1]}, Amount: {r[2]:.2f} EGPT, Wallet: {r[3]}, Date: {r[4]}\n"
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <withdraw_id>", reply_markup=main_keyboard())
        return
    withdraw_id = args[0]
    c.execute("SELECT user_id, amount_egpt FROM withdrawals WHERE id=? AND status='pending'", (withdraw_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("Withdraw request not found.", reply_markup=main_keyboard())
        return
    uid, amount = row
    micro_deduction = amount * (MICRO_TOKENS_TO_EGPT / 10)
    c.execute("SELECT micro_tokens FROM users WHERE user_id=?", (uid,))
    user_micro = c.fetchone()[0]
    new_micro = max(0, user_micro - micro_deduction)
    c.execute("UPDATE users SET micro_tokens=? WHERE user_id=?", (new_micro, uid))
    c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (withdraw_id,))
    conn.commit()
    await update.message.reply_text(f"Withdrawal {withdraw_id} approved. User {uid} balance updated.", reply_markup=main_keyboard())

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /reject <withdraw_id>", reply_markup=main_keyboard())
        return
    withdraw_id = args[0]
    c.execute("UPDATE withdrawals SET status='rejected' WHERE id=? AND status='pending'")
    conn.commit()
    await update.message.reply_text(f"Withdrawal {withdraw_id} rejected.", reply_markup=main_keyboard())

# -------- تشغيل البوت ----------
def main():
    TOKEN = "8594208349:AAF8BqZUWs9TCOqo3Lw7Jw3kxva7BBKruX4"  # ضع توكن البوت هنا
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
