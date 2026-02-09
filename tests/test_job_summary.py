import sys
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Schedule, Item, Source, JobSummary
from app.scheduler import process_due_schedules

from sqlalchemy.pool import StaticPool
# Mock database for testing
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    now = datetime.now(timezone.utc)
    
    # Create two sources
    s1 = Source(source_name="Source 1", active=True)
    s2 = Source(source_name="Source 2", active=True)
    session.add_all([s1, s2])
    session.flush()
    
    # Create two schedules
    sched1 = Schedule(name="Sched 1", frequency_type="minute", interval_value=1, active=True, next_run_time=now - timedelta(seconds=1))
    sched2 = Schedule(name="Sched 2", frequency_type="minute", interval_value=1, active=True, next_run_time=now - timedelta(seconds=1))
    session.add_all([sched1, sched2])
    session.flush()
    
    # Create items with rates
    items = [
        Item(name="I1", url="U1", schedule_id=sched1.id, source_id=s1.source_id, status="PENDING", active=True, rate=10.5),
        Item(name="I2", url="U2", schedule_id=sched1.id, source_id=s1.source_id, status="PENDING", active=True, rate=20.0),
        Item(name="I3", url="U3", schedule_id=sched1.id, source_id=s2.source_id, status="PENDING", active=True, rate=15.0),
        Item(name="I4", url="U4", schedule_id=sched2.id, source_id=s1.source_id, status="PENDING", active=True, rate=5.0),
        Item(name="I5", url="U5", schedule_id=sched2.id, source_id=None, status="PENDING", active=True, rate=None),
    ]
    session.add_all(items)
    session.commit()
    session.close()

def test_job_summary():
    setup_test_db()
    
    # Patch SessionLocal in app.scheduler to use our testing session
    import app.scheduler
    original_session_local = app.scheduler.SessionLocal
    app.scheduler.SessionLocal = TestingSessionLocal
    
    try:
        print("Running process_due_schedules...")
        process_due_schedules()
        
        # Check database
        session = TestingSessionLocal()
        summaries = session.query(JobSummary).all()
        
        print(f"Total summary rows: {len(summaries)}")
        assert len(summaries) == 1, f"Should have 1 summary row, found {len(summaries)}"
        summary = summaries[0]
        print(f"Job: {summary.job_id}, Start: {summary.start_time}, Items: {summary.num_of_items}")
        
        assert summary.num_of_items == 5, f"Expected 5 items, found {summary.num_of_items}"
        
        # Check ItemHistory
        from app.models import ItemHistory
        history_entries = session.query(ItemHistory).all()
        print(f"Total history entries: {len(history_entries)}")
        assert len(history_entries) == 5, f"Should have 5 history entries, found {len(history_entries)}"
        
        for h in history_entries:
            print(f"History - Job: {h.job_id}, Item: {h.item_id}, Price: {h.item_price}, Status: {h.status}")
            assert h.job_id == summary.job_id
            assert h.status == "DONE" # Scheduler calls mark_item_done which we updated
        
        # Verify specific prices
        i1 = session.query(Item).filter_by(name="I1").first()
        h1 = session.query(ItemHistory).filter_by(item_id=i1.id).first()
        assert h1.item_price == 10.5
        
        print("Verification successful: JobSummary is simplified and ItemHistory tracks individual items.")
        
    finally:
        app.scheduler.SessionLocal = original_session_local
        engine.dispose()

def test_rerun_and_failure():
    setup_test_db()
    session = TestingSessionLocal()
    
    # 1. Manually set one item to DONE, one to FAILED, one to DISABLED
    i1 = session.query(Item).filter_by(name="I1").first()
    i1.status = "DONE"
    i2 = session.query(Item).filter_by(name="I2").first()
    i2.status = "FAILED"
    i3 = session.query(Item).filter_by(name="I3").first()
    i3.status = "DISABLED"
    session.commit()
    
    print("\nStarting test_rerun_and_failure...")
    before_items = session.query(Item).all()
    print(f"Statuses before: { {item.name: item.status for item in before_items} }")
    session.close() # Close session to avoid lock or stale data
    
    # Patch SessionLocal
    import app.scheduler
    original_session_local = app.scheduler.SessionLocal
    app.scheduler.SessionLocal = TestingSessionLocal
    
    try:
        from unittest.mock import patch, MagicMock
        
        # Patch mark_item_done in the scheduler module
        # We want it to fail when it's called with status='DONE' for item I4
        original_mark_done = app.scheduler.mark_item_done
        
        def mock_mark_done(session, item_id, job_id, status='DONE'):
            # Find the item name for this item_id
            # Using a separate session to avoid interfering with the main one
            s = TestingSessionLocal()
            name = s.query(Item).get(item_id).name
            s.close()
            
            if name == "I4" and status == "DONE":
                raise Exception("SIMULATED PROCESSING ERROR for I4")
            return original_mark_done(session, item_id, job_id, status)
            
        with patch('app.scheduler.mark_item_done', side_effect=mock_mark_done):
            process_due_schedules()
        
        session = TestingSessionLocal()
        items = session.query(Item).all()
        status_map = {item.name: item.status for item in items}
        print(f"Statuses after: {status_map}")
        
        # Eligibility Check:
        # I1 (DONE) -> should be DONE (re-run)
        # I2 (FAILED) -> should be DONE (re-run)
        # I3 (DISABLED) -> should be DISABLED (skipped)
        # I4 (PENDING) -> should be FAILED (simulated error)
        # I5 (PENDING) -> should be DONE (run)
        
        assert status_map["I1"] == "DONE"
        assert status_map["I2"] == "DONE"
        assert status_map["I3"] == "DISABLED"
        assert status_map["I4"] == "FAILED"
        assert status_map["I5"] == "DONE"
        
        # Check ItemHistory for I4 failure
        from app.models import ItemHistory
        i4 = session.query(Item).filter_by(name="I4").first()
        history = session.query(ItemHistory).filter_by(item_id=i4.id).order_by(ItemHistory.id.desc()).first()
        assert history.status == "FAILED"
        
        print("Verification successful: DONE/FAILED items re-run, DISABLED items ignored, Errors recorded as FAILED.")

    finally:
        app.scheduler.SessionLocal = original_session_local
        session.close()

if __name__ == "__main__":
    test_job_summary()
    test_rerun_and_failure()
