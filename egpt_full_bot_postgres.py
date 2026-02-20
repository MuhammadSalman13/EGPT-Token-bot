import os
import psycopg2
from psycopg2.extras import RealDictCursor

# قراءة متغير البيئة DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("متغير البيئة DATABASE_URL مش موجود!")

try:
    # الاتصال بالقاعدة
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    print("✅ تم الاتصال بالقاعدة بنجاح!")

    # إنشاء جدول todos لو مش موجود
    create_table_query = """
    CREATE TABLE IF NOT EXISTS todos (
        id SERIAL PRIMARY KEY,
        task TEXT NOT NULL,
        completed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_table_query)
    conn.commit()
    print("✅ جدول todos جاهز!")

except Exception as e:
    print("❌ فشل الاتصال بالقاعدة:", e)

finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals():
        conn.close()
