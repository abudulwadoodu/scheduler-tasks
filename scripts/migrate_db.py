
import sqlite3
import os

DB_PATH = "scheduler.db"

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Adding 'rrule' column...")
        cursor.execute("ALTER TABLE schedule ADD COLUMN rrule TEXT")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipped: {e}")

    try:
        print("Adding 'start_time' column...")
        cursor.execute("ALTER TABLE schedule ADD COLUMN start_time DATETIME")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipped: {e}")

    try:
        print("Adding 'timezone' column...")
        cursor.execute("ALTER TABLE schedule ADD COLUMN timezone TEXT DEFAULT 'UTC'")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipped: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
