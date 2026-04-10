import sqlite3

db_path = "app.db"  # adjust if your DB is elsewhere

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE comment ADD COLUMN task_id INTEGER;")
    print("✅ Column 'task_id' added successfully.")
except Exception as e:
    print("⚠️ Error:", e)

conn.commit()
conn.close()
