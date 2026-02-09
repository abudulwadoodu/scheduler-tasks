import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Schedule, Item, Source, Script, JobSummary

def inspect_db():
    session = SessionLocal()
    
    print("\n--- Tables Summary ---")
    from sqlalchemy import inspect
    inspector = inspect(session.bind)
    print(f"Tables: {inspector.get_table_names()}")
    
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

    from app.models import ItemHistory
    print("\n--- Item History ---")
    history = session.query(ItemHistory).all()
    for h in history:
        print(f"Job: {h.job_id}, Sched: {h.schedule_id}, Item: {h.item_id}, Price: {h.item_price}, Status: {h.status}")

    session.close()

if __name__ == "__main__":
    inspect_db()
