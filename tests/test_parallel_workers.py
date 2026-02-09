import sys
import os
import threading
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Schedule, Item, Source, JobSummary
from app.procedures import pick_items_to_run, mark_item_done

# Mock database for testing
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    now = datetime.now(timezone.utc)
    
    # Create a schedule
    sched = Schedule(name="Parallel Sched", frequency_type="minute", interval_value=1, active=True, next_run_time=now - timedelta(seconds=1))
    session.add(sched)
    session.flush()
    
    # Create 20 items
    for i in range(20):
        item = Item(name=f"Item {i}", url=f"U{i}", schedule_id=sched.id, status="PENDING", active=True)
        session.add(item)
    
    session.commit()
    session.close()

def worker_task(worker_id, results):
    session = TestingSessionLocal()
    try:
        # Each worker tries to pick 5 items
        items = pick_items_to_run(session, batch_size=5)
        picked_ids = [item['id'] for item in items]
        results[worker_id] = picked_ids
        
        for item in items:
            # Simulate processing
            mark_item_done(session, item['id'], item['job_id'])
    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
    finally:
        session.close()

def test_parallel_pick():
    setup_test_db()
    
    # Patch SessionLocal in modules if necessary, but here we call procedures directly
    
    results = {}
    threads = []
    
    # Start 4 workers concurrently
    for i in range(4):
        t = threading.Thread(target=worker_task, args=(i, results))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Check results
    all_picked = []
    for worker_id, picked in results.items():
        print(f"Worker {worker_id} picked items: {picked}")
        all_picked.extend(picked)
    
    # Total items is 20, 4 workers picking 5 items each should get all 20 unique items
    assert len(all_picked) == 20, f"Expected 20 items picked, got {len(all_picked)}"
    assert len(set(all_picked)) == 20, "Each item should be picked by exactly one worker"
    
    # Verify JobSummary
    session = TestingSessionLocal()
    summaries = session.query(JobSummary).all()
    # In this test, each worker call to pick_items_to_run creates a JobSummary
    total_count = sum(s.num_of_items for s in summaries)
    assert total_count == 20, f"JobSummary total count should be 20, got {total_count}"
    
    # Verify ItemHistory
    from app.models import ItemHistory
    total_history = session.query(ItemHistory).filter_by(status='DONE').count()
    assert total_history == 20, f"ItemHistory total DONE count should be 20, got {total_history}"
    
    print("Verification successful: Concurrent workers picked unique items and updated JobSummary correctly.")
    session.close()

if __name__ == "__main__":
    test_parallel_pick()
    engine.dispose()
