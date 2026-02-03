
import sqlite3
import os

DB_PATH = "scheduler.db"

def verify_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables = ["sources", "scripts", "items"]
    
    for table in tables:
        print(f"\nSchema for {table}:")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            print(col)

    conn.close()

if __name__ == "__main__":
    verify_schema()
