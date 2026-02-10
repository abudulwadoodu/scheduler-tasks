from scheduler_core.db import SessionLocal
from scheduler_core.procedures import pick_items_to_run, mark_item_done
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler_core.config import Config



def process_due_schedules():
    session = SessionLocal()
    try:
        items_to_run = pick_items_to_run(session, batch_size=10)
        
        if not items_to_run:
            print("No due items to process.")
            return

        print(f"Processing batch of {len(items_to_run)} items.")

        for item_data in items_to_run:
            try:
                print(f"  Processing item: {item_data['name']} ({item_data['url']})")
                
                mark_item_done(
                    session, 
                    item_data['item_id'], 
                    item_data['job_id'],
                    status='DONE'
                )
                print(f"  Item {item_data['name']} marked DONE.")
                
            except Exception as e:
                print(f"  Error processing item {item_data['name']}: {e}")
                mark_item_done(
                    session, 
                    item_data['item_id'], 
                    item_data['job_id'],
                    status='FAILED'
                )
                print(f"  Item {item_data['name']} marked FAILED.")
                
    except Exception as e:
        print(f"Scheduler error: {e}")
    finally:
        session.close()
            
    session.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_due_schedules, 'interval', seconds=Config.INTERVAL_SECONDS)
    scheduler.start()
    print("Scheduler started...")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()
