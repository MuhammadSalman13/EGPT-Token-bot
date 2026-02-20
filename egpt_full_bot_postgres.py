import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time

# قراءة URL قاعدة البيانات من environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable is not set!")

# محاولة الاتصال بالقاعدة مع Retry
max_attempts = 5
for attempt in range(1, max_attempts + 1):
    try:
        print(f"Attempt {attempt}: Connecting to the database...")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("✅ Connected to the database!")
        break
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        if attempt == max_attempts:
            raise
        time.sleep(3)  # انتظار قبل إعادة المحاولة

# إنشاء جدول todos لو مش موجود
with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            task TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    print("✅ Table 'todos' is ready!")

# مثال تشغيل البوت (هنا تضع باقي الكود بتاع البوت)
print("🚀 Bot is now running...")
# هنا ضع كود التعامل مع Telegram أو أي واجهة ثانية
