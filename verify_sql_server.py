from scheduler_core.db import SessionLocal
from scheduler_core.models import Schedule, Item, Base
from scheduler_core.procedures import pick_items_to_run
from datetime import datetime, timezone, timedelta

def verify_procedure():
    session = SessionLocal()
    try:
        # 1. Clear existing data (optional, but good for clean test)
        session.query(Item).delete()
        session.query(Schedule).delete()
        
        # 2. Add a dummy schedule
        now = datetime.now(timezone.utc)
        sched = Schedule(
            name="Test Schedule",
            frequency_type="MINUTES",
            interval_value=1,
            active=True,
            next_run_time=now - timedelta(minutes=1) # Due now
        )
        session.add(sched)
        session.flush()
        
        # 3. Add a dummy item
        item = Item(
            name="Test Item",
            item_code="TEST001",
            url="http://example.com",
            schedule_id=sched.id,
            status="PENDING",
            active=True
        )
        session.add(item)
        session.commit()
        
        print("Inserted test data.")

        # 4. Call the migrated procedure
        print("Calling pick_items_to_run...")
        items = pick_items_to_run(session, batch_size=5)
        
        if items and len(items) > 0:
            print(f"Success! Picked {len(items)} items.")
            print(f"Item 1 Data: {items[0]}")
            
            # Check if status was updated in DB
            db_item = session.query(Item).filter_by(id=items[0]['item_id']).first()
            print(f"DB Item Status: {db_item.status}")
            if db_item.status == 'RUNNING':
                print("Verification PASSED: Item status updated to RUNNING.")
            else:
                print(f"Verification FAILED: Expected status RUNNING, got {db_item.status}")
        else:
            print("Verification FAILED: No items picked.")

    except Exception as e:
        print(f"An error occurred during verification: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    verify_procedure()
