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

# Mock database for testing
TEST_DB_URL = "sqlite:///test_job_summary.db"
engine = create_engine(TEST_DB_URL)
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
    
    # Create items
    # Sched 1: 2 items from Source 1, 1 item from Source 2
    # Sched 2: 1 item from Source 1, 1 item with NO source
    items = [
        Item(name="I1", url="U1", schedule_id=sched1.id, source_id=s1.source_id, status="PENDING", active=True),
        Item(name="I2", url="U2", schedule_id=sched1.id, source_id=s1.source_id, status="PENDING", active=True),
        Item(name="I3", url="U3", schedule_id=sched1.id, source_id=s2.source_id, status="PENDING", active=True),
        Item(name="I4", url="U4", schedule_id=sched2.id, source_id=s1.source_id, status="PENDING", active=True),
        Item(name="I5", url="U5", schedule_id=sched2.id, source_id=None, status="PENDING", active=True),
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
        for s in summaries:
            print(f"Job: {s.job_id}, Sched: {s.schedule_id}, Source: {s.source_id}, Count: {s.item_count}")
        
        # Check counts
        # (Sched1, Source1) -> 2
        # (Sched1, Source2) -> 1
        # (Sched2, Source1) -> 1
        # (Sched2, None) -> 1
        assert len(summaries) == 4, f"Should have 4 summary rows, found {len(summaries)}"
        
        job_ids = set(s.job_id for s in summaries)
        assert len(job_ids) == 1, "All summaries in one batch should have the same job_id"
        job_id = list(job_ids)[0]
        assert isinstance(job_id, int), f"job_id should be an integer, got {type(job_id)}"
        assert job_id >= 1, f"job_id should be >= 1, got {job_id}"
        
        # Verify specific counts
        summary_map = {(s.schedule_id, s.source_id): s.item_count for s in summaries}
        
        s1_id = session.query(Source).filter_by(source_name="Source 1").first().source_id
        s2_id = session.query(Source).filter_by(source_name="Source 2").first().source_id
        sched1_id = session.query(Schedule).filter_by(name="Sched 1").first().id
        sched2_id = session.query(Schedule).filter_by(name="Sched 2").first().id

        assert summary_map[(sched1_id, s1_id)] == 2
        assert summary_map[(sched1_id, s2_id)] == 1
        assert summary_map[(sched2_id, s1_id)] == 1
        assert summary_map[(sched2_id, None)] == 1
        
        print("Verification successful: Multiple rows share the same job_id and counts are accurate.")
        
    finally:
        app.scheduler.SessionLocal = original_session_local
        engine.dispose()
        if os.path.exists("test_job_summary.db"):
            try:
                os.remove("test_job_summary.db")
            except Exception as e:
                print(f"Cleanup error: {e}")

if __name__ == "__main__":
    test_job_summary()
