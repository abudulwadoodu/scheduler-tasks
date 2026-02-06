from app.db import SessionLocal
from app.models import Schedule, Item, JobSummary
from app.services import calculate_next_run
from sqlalchemy import func
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

def process_due_schedules():
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    
    # Derive next job_id from JobSummary
    last_job_id = session.query(func.max(JobSummary.job_id)).scalar() or 0
    job_id = last_job_id + 1
    
    print(f"Starting scheduler batch: {job_id}")

    schedules = session.query(Schedule)\
        .filter(Schedule.active == True)\
        .filter(Schedule.next_run_time <= now)\
        .all()

    for sched in schedules:
        print(f"Running schedule: {sched.name}")

        # Update next_run_time immediately when an interval begins
        sched.last_run_time = now
        sched.next_run_time = calculate_next_run(sched, now)
        session.commit()
        print(f"  Advancing schedule {sched.name}. Next run: {sched.next_run_time}")

        # Check for pending items
        pending_count = session.query(Item)\
            .filter(Item.schedule_id == sched.id)\
            .filter(Item.active == True)\
            .filter(Item.status == 'PENDING')\
            .count()

        # If no pending items, it means we are starting a NEW cycle.
        # Reset all items to PENDING.
        if pending_count == 0:
            print(f"  Starting new cycle for {sched.name}. Resetting items to PENDING.")
            session.query(Item)\
                .filter(Item.schedule_id == sched.id)\
                .filter(Item.active == True)\
                .update({"status": 'PENDING'}, synchronize_session=False)
            session.commit()

        # Fetch pending items (limited batch size could be applied here)
        items = session.query(Item)\
            .filter(Item.schedule_id == sched.id)\
            .filter(Item.active == True)\
            .filter(Item.status == 'PENDING')\
            .all()

        all_items_processed = True
        
        for item in items:
            try:
                print(f"  Processing item: {item.name} ({item.url})")
                # Simulate processing work
                item.last_run_time = datetime.now(timezone.utc)
                item.status = "DONE"
                
                # Update Job Summary
                summary = session.query(JobSummary).filter_by(
                    job_id=job_id,
                    schedule_id=sched.id,
                    source_id=item.source_id
                ).first()

                if not summary:
                    summary = JobSummary(
                        job_id=job_id,
                        schedule_id=sched.id,
                        source_id=item.source_id,
                        item_count=1
                    )
                    session.add(summary)
                else:
                    summary.item_count += 1

                # Checkpoint: Commit immediately so we don't lose progress on crash
                session.commit()
            except Exception as e:
                print(f"  Error processing item {item.name}: {e}")
                session.rollback()
                all_items_processed = False
                # Optionally break or continue based on policy

        # Remaining pending check is no longer used for next_run_time update
        # but could be useful for logging or other logic if needed.
        remaining_pending = session.query(Item)\
            .filter(Item.schedule_id == sched.id)\
            .filter(Item.active == True)\
            .filter(Item.status == 'PENDING')\
            .count()

        if remaining_pending == 0:
            print(f"  All items processed for schedule {sched.name}.")
            
    session.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_due_schedules, 'interval', seconds=30)
    scheduler.start()
    print("Scheduler started...")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()
