from sqlalchemy import text, func
from app.models import Item, Schedule, Source, JobSummary
from datetime import datetime, timezone

def pick_items_to_run(session, batch_size=10):
    """
    Simulates 'Stored Procedure 1': Selects due items, marks them as RUNNING,
    and returns them with required batch metadata.
    """
    now = datetime.now(timezone.utc)
    
    # 1. Advance next_run_time for due schedules
    # (Matches requirement: Update next_run_time immediately when interval begins)
    from app.services import calculate_next_run
    due_schedules = session.query(Schedule).filter(
        Schedule.active == True,
        Schedule.next_run_time <= now
    ).all()
    
    if not due_schedules:
        return []

    due_schedule_ids = [s.id for s in due_schedules]
    
    for sched in due_schedules:
        # Advance schedule (only if last_run_time hasn't been updated to 'now' yet)
        if sched.last_run_time != now:
            sched.last_run_time = now
            sched.next_run_time = calculate_next_run(sched, now)
    
    session.flush() # Flush changes to schedules to the session

    # 2. Derive next job_id
    last_job_id = session.query(func.max(JobSummary.job_id)).scalar() or 0
    job_id = last_job_id + 1
    
    # 3. Select and Mark items as RUNNING atomically.
    placeholders = ", ".join(f":id_{i}" for i in range(len(due_schedule_ids)))
    query_text = f"""
    UPDATE items 
    SET status = 'RUNNING',
        last_run_time = :now
    WHERE id IN (
        SELECT i.id 
        FROM items i
        WHERE i.active = 1 
          AND i.schedule_id IN ({placeholders})
          AND i.status NOT IN ('RUNNING', 'DISABLED')
        ORDER BY i.last_run_time ASC NULLS FIRST
        LIMIT :batch_size
    )
    RETURNING id, schedule_id, source_id, item_code, name, url, rate;
    """
    query = text(query_text)
    
    params = {"now": now, "batch_size": batch_size}
    for i, sid in enumerate(due_schedule_ids):
        params[f"id_{i}"] = sid
        
    result = session.execute(query, params).fetchall()
    
    # 4. Initialize JobSummary and ItemHistory
    if result:
        from app.models import ItemHistory
        
        job_summary = JobSummary(
            job_id=job_id,
            start_time=now,
            num_of_items=len(result)
        )
        session.add(job_summary)
        
        items_to_run = []
        for row in result:
            history = ItemHistory(
                job_id=job_id,
                schedule_id=row.schedule_id,
                item_id=row.id,
                item_price=row.rate,
                status='RUNNING'
            )
            session.add(history)
            
            items_to_run.append({
                "job_id": job_id,
                "id": row.id,
                "schedule_id": row.schedule_id,
                "source_id": row.source_id,
                "item_code": row.item_code,
                "name": row.name,
                "url": row.url,
                "rate": row.rate
            })

        session.commit()
    else:
        items_to_run = []
        
    return items_to_run

def mark_item_done(session, item_id, job_id, status='DONE'):
    """
    Simulates 'Stored Procedure 2': Marks item with final status and updates ItemHistory.
    """
    from app.models import ItemHistory
    
    # 1. Update item status
    session.query(Item).filter(Item.id == item_id).update({"status": status})
    
    # 2. Update ItemHistory
    session.query(ItemHistory).filter_by(
        job_id=job_id,
        item_id=item_id
    ).update({"status": status})
        
    session.commit()
