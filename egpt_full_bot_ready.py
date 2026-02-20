# egpt_full_bot_postgres_final.py
import os
import asyncpg
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime
import asyncio

# -------- إعدادات البوت ----------
MICRO_TOKENS_PER_TAP = 10000
MICRO_TOKENS_DAILY_MAX = 500000
MICRO_TOKENS_CHECKIN = 50000
MICRO_TOKENS_INVITE = 100000
MICRO_TOKENS_TO_EGPT = 1000000  # 1,000,000 Micro = 10 EGPT
WITHDRAW_MIN_EGPT = 100
INVITE_REQUIREMENT = 10
ADMIN_IDS = [5808513261]  # ضع Telegram ID الخاص بك
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

# -------- الاتصال بقاعدة البيانات ----------
async def get_db_pool():
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "password")
    DB_NAME = os.getenv("DB_NAME", "egpt_db")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    return await asyncpg.create_pool(user=DB_USER, password=DB_PASS, database=DB_NAME, host=DB_HOST, port=DB_PORT)

# -------- تهيئة الجداول ----------
async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            micro_tokens BIGINT DEFAULT 0,
            last_tap TEXT,
            last_checkin TEXT,
            invited_count INT DEFAULT 0,
            wallet_address TEXT
        );
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount_egpt REAL,
            wallet_address TEXT,
            status TEXT DEFAULT 'pending',
            request_date TEXT
        );
        ''')

# -------- بدء البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pool = context.bot_data["db_pool"]
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING;", user_id)
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=WELCOME_KEYBOARD)

# -------- التعامل مع الرسائل من المستخدم --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    pool = context.bot_data["db_pool"]

    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING;", user_id)
        row = await conn.fetchrow("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=$1;", user_id)
        micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
        now = datetime.now().strftime("%Y-%m-%d")

        if text == "💰 Earn":
            daily_tokens = micro_tokens if last_tap == now else 0
            daily_tokens += MICRO_TOKENS_PER_TAP
            if daily_tokens > MICRO_TOKENS_DAILY_MAX:
                daily_tokens = MICRO_TOKENS_DAILY_MAX
            await conn.execute("UPDATE users SET micro_tokens=$1, last_tap=$2 WHERE user_id=$3;", daily_tokens, now, user_id)
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
            await conn.execute("UPDATE users SET micro_tokens=$1, last_checkin=$2 WHERE user_id=$3;", micro_tokens, now, user_id)
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
            await conn.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES($1,$2,$3,$4);", user_id, egpt_balance, wallet_address, now)
            await update.message.reply_text(f"Your withdraw request of {egpt_balance:.2f} EGPT has been submitted and is pending approval by admin.", reply_markup=WELCOME_KEYBOARD)

        elif text.startswith("0x") and len(text) == 42:
            await conn.execute("UPDATE users SET wallet_address=$1 WHERE user_id=$2;", text, user_id)
            await update.message.reply_text("Wallet address saved successfully!", reply_markup=WELCOME_KEYBOARD)

        else:
            await update.message.reply_text("Invalid input. Use the buttons below.", reply_markup=WELCOME_KEYBOARD)

# -------- أوامر Admin كاملة ----------
async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    pool = context.bot_data["db_pool"]
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, user_id, amount_egpt, wallet_address, request_date FROM withdrawals WHERE status='pending';")
    if not rows:
        await update.message.reply_text("No pending withdrawals.", reply_markup=WELCOME_KEYBOARD)
        return
    msg = "Pending Withdrawals:\n"
    for r in rows:
        msg += f"ID: {r[0]}, User: {r[1]}, Amount: {r[2]:.2f} EGPT, Wallet: {r[3]}, Date: {r[4]}\n"
    await update.message.reply_text(msg, reply_markup=WELCOME_KEYBOARD)

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <withdraw_id>", reply_markup=WELCOME_KEYBOARD)
        return
    withdraw_id = args[0]
    pool = context.bot_data["db_pool"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id, amount_egpt FROM withdrawals WHERE id=$1 AND status='pending';", withdraw_id)
        if not row:
            await update.message.reply_text("Withdraw request not found.", reply_markup=WELCOME_KEYBOARD)
            return
        uid, amount = row
        micro_deduction = amount * (MICRO_TOKENS_TO_EGPT / 10)
        user_row = await conn.fetchrow("SELECT micro_tokens FROM users WHERE user_id=$1;", uid)
        new_micro = max(0, user_row[0] - micro_deduction)
        await conn.execute("UPDATE users SET micro_tokens=$1 WHERE user_id=$2;", new_micro, uid)
        await conn.execute("UPDATE withdrawals SET status='approved' WHERE id=$1;", withdraw_id)
    await update.message.reply_text(f"Withdrawal {withdraw_id} approved. User {uid} balance updated.", reply_markup=WELCOME_KEYBOARD)

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /reject <withdraw_id>", reply_markup=WELCOME_KEYBOARD)
        return
    withdraw_id = args[0]
    pool = context.bot_data["db_pool"]
    async with pool.acquire() as conn:
        await conn.execute("UPDATE withdrawals SET status='rejected' WHERE id=$1 AND status='pending';", withdraw_id)
    await update.message.reply_text(f"Withdrawal {withdraw_id} rejected.", reply_markup=WELCOME_KEYBOARD)

# -------- أمر Admin لعرض كل المستخدمين مع صفحات ----------
async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.", reply_markup=WELCOME_KEYBOARD)
        return

    page = int(context.args[0]) if context.args else 0
    pool = context.bot_data["db_pool"]
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users ORDER BY user_id;")

    users_per_page = 10
    total_pages = (len(rows) - 1) // users_per_page + 1
    start_index = page * users_per_page
    end_index = start_index + users_per_page
    page_rows = rows[start_index:end_index]

    msg = f"Users List (Page {page+1}/{total_pages}):\n"
    for r in page_rows:
        msg += (f"User ID: {r[0]}, Micro: {r[1]}, Last Tap: {r[2]}, Check-in: {r[3]}, Invited: {r[4]}, Wallet: {r[5]}\n")

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"users_page_{page-1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_page_{page+1}"))
    keyboard = InlineKeyboardMarkup([buttons]) if buttons else None
    await update.message.reply_text(msg, reply_markup=keyboard)

async def users_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("users_page_"):
        page = int(data.split("_")[-1])
        context.args = [str(page)]
        await admin_list_users(update, context)

# -------- تشغيل البوت ----------
async def main():
    TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    pool = await get_db_pool()
    await init_db(pool)

    app = ApplicationBuilder().token(TOKEN).build()
    app.bot_data["db_pool"] = pool

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", admin_list_users))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.CallbackQuery.ALL, users_pagination_callback))

    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
