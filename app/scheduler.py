from app.db import SessionLocal
from app.models import Schedule, Item
from app.services import calculate_next_run
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

def process_due_schedules():
    session = SessionLocal()
    now = datetime.now(timezone.utc)

    schedules = session.query(Schedule)\
        .filter(Schedule.active == True)\
        .filter(Schedule.next_run_time <= now)\
        .all()

    for sched in schedules:
        print(f"Running schedule: {sched.name}")

        # Process items under this schedule
        items = session.query(Item)\
            .filter(Item.schedule_id == sched.id)\
            .filter(Item.active == True)\
            .all()

        for item in items:
            print(f"  Processing item: {item.name}")
            item.last_run_time = now
            item.status = "DONE"

        sched.last_run_time = now
        sched.next_run_time = calculate_next_run(sched, now)

    session.commit()
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
