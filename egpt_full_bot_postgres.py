import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time

# اقرأ الـ DATABASE_URL من environment variables
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL غير معرف في المتغيرات")

# حاول الاتصال بالقاعدة مع retries بسيطة
max_attempts = 5
for attempt in range(1, max_attempts + 1):
    try:
        print(f"Attempt {attempt}: Connecting to the database...")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("✅ Connected to Postgres successfully!")
        break
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        if attempt < max_attempts:
            print("Retrying in 3 seconds...")
            time.sleep(3)
        else:
            raise e

# تأكد أن جدول todos موجود، وإن لم يكن فأنشئه
cursor.execute("""
CREATE TABLE IF NOT EXISTS todos (
    id SERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
print("✅ Table 'todos' is ready!")

# مثال بسيط لتشغيل البوت
def start_bot():
    print("🤖 Bot is now running...")
    # هنا ضع الكود الرئيسي للبوت (التعامل مع Telegram API مثلاً)
    # مثال:
    while True:
        # هذه مجرد محاكاة للـ loop الرئيسي
        time.sleep(10)

if __name__ == "__main__":
    start_bot()
