import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor

# اقرأ الـ DATABASE_URL من environment
DATABASE_URL = os.environ.get("DATABASE_URL")

# عدد المحاولات قبل الفشل
MAX_RETRIES = 5
RETRY_DELAY = 5  # ثواني بين المحاولات

conn = None
for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"Attempt {attempt}: Connecting to the database...")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("✅ Database connection successful!")
        break
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        if attempt < MAX_RETRIES:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
        else:
            print("❌ All retries failed. Exiting.")
            raise e

# تأكد إن الجدول موجود
with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            task TEXT NOT NULL,
            done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    print("✅ Table 'todos' is ready.")

# هنا تبدأ شيفرة البوت
# مثال dummy loop لتأكيد التشغيل
try:
    while True:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM todos;")
            count = cur.fetchone()['count']
            print(f"📝 Total todos: {count}")
        time.sleep(10)
except KeyboardInterrupt:
    print("Stopping bot...")

# اغلق الاتصال عند الانتهاء
finally:
    if conn:
        conn.close()
        print("✅ Database connection closed.")
