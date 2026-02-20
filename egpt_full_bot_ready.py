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

def get_keyboard(user_id):
    kb = [
        ["💰 Earn", "📊 Balance"],
        ["👥 Referrals", "🎁 Daily Check-in"],
        ["💳 Set Wallet", "💸 Withdraw"]
    ]
    if user_id in ADMIN_IDS:
        kb.append(["🔧 Admin"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

WELCOME_MESSAGE = "مرحبا بك في EGPT Bot! استخدم الأزرار أدناه للوصول لجميع المزايا."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=get_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    micro_tokens = last_tap = last_checkin = invited_count = wallet_address = 0
    if row:
        micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
    now = datetime.now().strftime("%Y-%m-%d")
    kb = get_keyboard(user_id)

    if text == "🔧 Admin" and user_id in ADMIN_IDS:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT SUM(micro_tokens) FROM users")
        total_balance = c.fetchone()[0] or 0
        c.execute("SELECT user_id, micro_tokens FROM users ORDER BY micro_tokens DESC LIMIT 5")
        top_users = c.fetchall()
        c.execute("SELECT id, user_id, amount_egpt, status FROM withdrawals ORDER BY id DESC LIMIT 5")
        withdraws = c.fetchall()
        
        msg = f"🔧 لوحة التحكم:
"
        msg += f"👥 المستخدمين: {total_users}
"
        msg += f"💰 الرصيد الكلي: {total_balance:,}

"
        msg += f"🏆 أعلى 5:
"
        for u in top_users:
            egpt = u[1] / MICRO_TOKENS_TO_EGPT * 10
            msg += f"ID {u[0]}: {u[1]:,} ({egpt:.1f}EGPT)
"
        msg += f"
💸 آخر 5 سحوبات:
"
        for w in withdraws:
            msg += f"ID {w[0]}: User {w[1]} ({w[2]:.1f}EGPT) {w[3]}
"
        
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup([["🔙 Back", "📋 Pending"]], resize_keyboard=True))
        return

    if text == "🔙 Back" and user_id in ADMIN_IDS:
        await update.message.reply_text("🔙 العودة:", reply_markup=kb)
        return

    if text == "📋 Pending" and user_id in ADMIN_IDS:
        c.execute("SELECT * FROM withdrawals WHERE status='pending'")
        rows = c.fetchall()
        msg = "المعلقة:
"
        if rows:
            for r in rows:
                msg += f"{r[0]}: User{r[1]} {r[2]:.1f}EGPT
"
        else:
            msg += "لا يوجد"
        await update.message.reply_text(msg, reply_markup=kb)
        return

    if text == "💰 Earn":
        daily_tokens = micro_tokens if last_tap == now else 0
        daily_tokens += MICRO_TOKENS_PER_TAP
        if daily_tokens > MICRO_TOKENS_DAILY_MAX:
            daily_tokens = MICRO_TOKENS_DAILY_MAX
        c.execute("UPDATE users SET micro_tokens=?, last_tap=? WHERE user_id=?", (daily_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ +{MICRO_TOKENS_PER_TAP} Micro! اليوم: {daily_tokens}", reply_markup=kb)

    elif text == "📊 Balance":
        egpt = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        wallet_info = wallet_address or "غير محدد"
        await update.message.reply_text(f"رصيدك:
Micro: {micro_tokens:,}
EGPT: {egpt:.2f}
أصدقاء: {invited_count}
محفظة: {wallet_info}", reply_markup=kb)

    elif text == "👥 Referrals":
        link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(f"عنوان الدعوة:
{link}
كل صديق = {MICRO_TOKENS_INVITE} Micro", reply_markup=kb)

    elif text == "🎁 Daily Check-in":
        if last_checkin == now:
            await update.message.reply_text("✅ تم الチェック اليومي!", reply_markup=kb)
            return
        micro_tokens += MICRO_TOKENS_CHECKIN
        c.execute("UPDATE users SET micro_tokens=?, last_checkin=? WHERE user_id=?", (micro_tokens, now, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ Check-in: +{MICRO_TOKENS_CHECKIN}
الكلي: {micro_tokens:,}", reply_markup=kb)

    elif text == "💳 Set Wallet":
        await update.message.reply_text("📤 أرسل عنوان USDT BSC:", reply_markup=kb)

    elif text == "💸 Withdraw":
        egpt_balance = micro_tokens / MICRO_TOKENS_TO_EGPT * 10
        if egpt_balance < WITHDRAW_MIN_EGPT:
            await update.message.reply_text(f"الحد الأدنى: {WITHDRAW_MIN_EGPT} EGPT
رصيدك: {egpt_balance:.2f}", reply_markup=kb)
            return
        if not wallet_address:
            await update.message.reply_text("حدد المحفظة أولاً!", reply_markup=kb)
            return
        c.execute("INSERT INTO withdrawals(user_id, amount_egpt, wallet_address, request_date) VALUES (?,?,?,?)", (user_id, egpt_balance, wallet_address, now))
        conn.commit()
        await update.message.reply_text(f"✅ طلب سحب {egpt_balance:.2f} EGPT ▶ انتظار الموافقة", reply_markup=kb)

    elif text.startswith("0x") and len(text) == 42:
        c.execute("UPDATE users SET wallet_address=? WHERE user_id=?", (text, user_id))
        conn.commit()
        await update.message.reply_text("✅ المحفظة محفوظة!", reply_markup=kb)

    else:
        await update.message.reply_text("استخدم الأزرار أسفل!", reply_markup=kb)

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS: return
    c.execute("SELECT * FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    msg = "المعلقة:
"
    if rows:
        for r in rows:
            msg += f"{r[0]}: User{r[1]} {r[2]:.1f}EGPT
"
    else:
        msg += "لا يوجد"
    await update.message.reply_text(msg)

async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS: return
    if context.args:
        wid = context.args[0]
        c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (wid,))
        conn.commit()
        await update.message.reply_text(f"✅ موافقة: {wid}")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS: return
    if context.args:
        wid = context.args[0]
        c.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
        conn.commit()
        await update.message.reply_text(f"❌ مرفوض: {wid}")

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
