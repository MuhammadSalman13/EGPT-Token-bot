# egpt_full_bot_ready_v2.py  (النسخة المعدلة v3)
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, CallbackQueryHandler, filters
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
ADMIN_IDS = [123456789]  # غيّر إلى Telegram ID الخاص بك هنا!
BOT_USERNAME = "EGPTCOINSBot"  # اسم البوت بدون @

# -------- قائمة الترحيب الديناميكية (Admin فقط) ----------
def get_welcome_keyboard(user_id):
    keyboard = [
        ["💰 Earn", "📊 Balance"],
        ["👥 Referrals", "🎁 Daily Check-in"],
        ["💳 Set Wallet", "💸 Withdraw"]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append(["🔧 Admin"])  # الزر الجديد للأدمن فقط!
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

WELCOME_MESSAGE = "مرحبًا بك في EGPT Bot!
استخدم الأزرار أدناه للوصول لجميع المزايا."

# -------- بدء البوت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    keyboard = get_welcome_keyboard(user_id)
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=keyboard)

# -------- التعامل مع الرسائل من المستخدم --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()
    c.execute("SELECT micro_tokens, last_tap, last_checkin, invited_count, wallet_address FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        micro_tokens, last_tap, last_checkin, invited_count, wallet_address = row
    else:
        micro_tokens = last_tap = last_checkin = invited_count = wallet_address = 0
    now = datetime.now().strftime("%Y-%m-%d")

    # -------- لوحة الأدمن الجديدة 🔧 --------
    if text == "🔧 Admin" and user_id in ADMIN_IDS:
        # عدد المستخدمين
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        # نشاط (آخر tap/checkin للأوائل 10)
        c.execute("SELECT user_id, last_tap, last_checkin FROM users ORDER BY last_tap DESC LIMIT 10")
        activity = c.fetchall()
        
        # رصيد (إجمالي + أعلى 5)
        c.execute("SELECT SUM(micro_tokens), COUNT(*) FROM users WHERE micro_tokens > 0")
        total_balance, active_users = c.fetchone()
        c.execute("SELECT user_id, micro_tokens FROM users ORDER BY micro_tokens DESC LIMIT 5")
        top_balances = c.fetchall()
        
        # طلبات السحب
        c.execute("SELECT id, user_id, amount_egpt, status, request_date FROM withdrawals ORDER BY request_date DESC LIMIT 10")
        withdraws = c.fetchall()
        
        msg = f"🔧 لوحة الأدمن:
"
        msg += f"👥 عدد المستخدمين: {total_users}
"
        msg += f"💰 إجمالي الرصيد: {total_balance or 0:,} Micro
"
        msg += f"📈 نشاط (آخر 10):
"
        for act in activity:
            msg += f"User {act[0]}: Tap {act[1]}, Check {act[2]}
"
        msg += f"
🏆 أعلى 5 رصيد:
"
        for bal in top_balances:
            egpt = bal[1] / MICRO_TOKENS_TO_EGPT * 10
            msg += f"User {bal[0]}: {bal[1]:,} Micro ({egpt:.2f} EGPT)
"
        msg += f"
💸 طلبات السحب (آخر 10):
"
        for w in withdraws:
            msg += f"ID {w[0]} | User {w[1]} | {w[2]:.2f} EGPT | {w[3]} | {w[4]}
"
        
        keyboard = ReplyKeyboardMarkup([["📋 Pending Only", "🔙 Back"]], resize_keyboard=True)
        await update.message.reply_text(msg, reply_markup=keyboard)
        return

    elif text == "📋 Pending Only" and user_id in ADMIN_IDS:
        c.execute("SELECT id, user_id, amount_egpt, wallet_address, request_
