from scheduler_core.db import engine
from scheduler_core.models import Base

def init_db():
    print(f"Connecting to database at: {engine.url}")
    try:
        Base.metadata.create_all(engine)
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
