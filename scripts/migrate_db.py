
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

    # Create sources table
    try:
        print("Creating 'sources' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT,
                source_type TEXT,
                base_url TEXT,
                login_required BOOLEAN DEFAULT 0,
                active BOOLEAN DEFAULT 1,
                last_crawled_at DATETIME,
                created_at DATETIME,
                schedule_id INTEGER,
                FOREIGN KEY (schedule_id) REFERENCES schedule (id)
            )
        """)
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Error creating sources table: {e}")

    # Create scripts table
    try:
        print("Creating 'scripts' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                type TEXT,
                path TEXT,
                FOREIGN KEY (source_id) REFERENCES sources (source_id)
            )
        """)
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Error creating scripts table: {e}")

    # Add columns to items table
    item_columns = [
        ("source_id", "INTEGER"),
        ("rate", "REAL"),
        ("last_price_updated_at", "DATETIME"),
        ("remarks", "TEXT"),
        ("no_of_revisions", "INTEGER DEFAULT 0"),
        ("prompt_details", "TEXT"),
        ("comments", "TEXT"),
        ("script_id", "INTEGER"),
        ("instant_flag", "BOOLEAN DEFAULT 0"),
        ("item_type", "TEXT")
    ]

    for col_name, col_type in item_columns:
        try:
            print(f"Adding '{col_name}' column to items...")
            cursor.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}")
            print("Success.")
        except sqlite3.OperationalError as e:
            print(f"Skipped {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
