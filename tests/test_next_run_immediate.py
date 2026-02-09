import sys
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Schedule, Item
from app.scheduler import process_due_schedules

# Mock database for testing
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    now = datetime.now(timezone.utc)
    
    # Create a schedule that is due
    schedule = Schedule(
        name="Test Schedule",
        frequency_type="minute",
        interval_value=1,
        active=True,
        next_run_time=now - timedelta(seconds=10)
    )
    session.add(schedule)
    session.flush()
    
    # Create one item for the schedule
    item = Item(
        name="Test Item",
        url="http://example.com",
        schedule_id=schedule.id,
        status="PENDING",
        active=True
    )
    session.add(item)
    session.commit()
    
    schedule_id = schedule.id
    old_next_run = schedule.next_run_time
    session.close()
    return schedule_id, old_next_run

def test_immediate_update():
    schedule_id, old_next_run = setup_test_db()
    
    # Patch SessionLocal in app.scheduler to use our testing session
    import app.scheduler
    original_session_local = app.scheduler.SessionLocal
    app.scheduler.SessionLocal = TestingSessionLocal
    
    try:
        print("Running process_due_schedules...")
        process_due_schedules()
        
        # Check database
        session = TestingSessionLocal()
        sched = session.query(Schedule).get(schedule_id)
        
        print(f"Old next_run_time: {old_next_run}")
        print(f"New next_run_time: {sched.next_run_time}")
        
        assert sched.next_run_time > old_next_run, "next_run_time should have advanced"
        
        # Check if item was processed (it should be, but next_run_time was advanced FIRST)
        item = session.query(Item).filter(Item.schedule_id == schedule_id).first()
        assert item.status == "DONE", "Item should be DONE"
        
        print("Verification successful: next_run_time advanced and items were processed.")
        
    finally:
        app.scheduler.SessionLocal = original_session_local
        if 'session' in locals():
            session.close()
        engine.dispose()

if __name__ == "__main__":
    test_immediate_update()
