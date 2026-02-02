
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Schedule, Item
from datetime import datetime, timezone, timedelta

def simulate_interruption():
    session = SessionLocal()
    now = datetime.now(timezone.utc)

    # 1. Find the "Every 1 Minute" schedule
    schedule = session.query(Schedule).filter(Schedule.name == "Every 1 Minute").first()
    if not schedule:
        print("Schedule 'Every 1 Minute' not found.")
        return

    # 2. Force status due
    schedule.next_run_time = now - timedelta(minutes=1)
    
    # 3. Get items
    items = session.query(Item).filter(Item.schedule_id == schedule.id).order_by(Item.id).all()
    print(f"Found {len(items)} items for '{schedule.name}'.")

    # 4. Update via session.query().update() for safety
    half_index = len(items) // 2
    ids_to_done = [item.id for item in items[:half_index]]
    ids_to_pending = [item.id for item in items[half_index:]]

    if ids_to_done:
        session.query(Item).filter(Item.id.in_(ids_to_done)).update({"status": "DONE", "last_run_time": now}, synchronize_session=False)
        print(f"Marked {len(ids_to_done)} items as DONE.")

    if ids_to_pending:
        session.query(Item).filter(Item.id.in_(ids_to_pending)).update({"status": "PENDING"}, synchronize_session=False)
        print(f"Marked {len(ids_to_pending)} items as PENDING.")

    try:
        session.commit()
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()

    print("\nSimulation setup complete.")
    print(f"Schedule '{schedule.name}' is DUE.")
    print("Run the scheduler now. It should ONLY process the PENDING items.")
    session.close()

if __name__ == "__main__":
    simulate_interruption()
