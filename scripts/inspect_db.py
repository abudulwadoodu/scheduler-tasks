
from app.db import SessionLocal
from app.models import Schedule, Item, Source, Script

def inspect_db():
    session = SessionLocal()
    
    print("\n--- Schedules ---")
    schedules = session.query(Schedule).all()
    for s in schedules:
        print(f"ID: {s.id}, Name: {s.name}")

    print("\n--- Items ---")
    items = session.query(Item).all()
    for i in items:
        print(f"ID: {i.id}, Name: {i.name}, URL: {i.url}, Type: {i.item_type}")

    print("\n--- Sources ---")
    sources = session.query(Source).all()
    for s in sources:
        print(f"ID: {s.source_id}, Name: {s.source_name}")

    print("\n--- Scripts ---")
    scripts = session.query(Script).all()
    for s in scripts:
        print(f"ID: {s.id}, Source ID: {s.source_id}, Type: {s.type}, Path: {s.path}")

    session.close()

if __name__ == "__main__":
    inspect_db()
