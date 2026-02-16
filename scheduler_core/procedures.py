from sqlalchemy import text, func
from scheduler_core.models import Item, Schedule, Source, JobSummary, Script
from datetime import datetime, timezone

def pick_items_to_run(session, batch_size=10):
    """
    Simulates 'Stored Procedure 1': Selects due items, marks them as RUNNING,
    and returns them with required batch metadata.
    """
    now = datetime.now(timezone.utc)
    
    # 1. Advance next_run_time for due schedules
    # (Matches requirement: Update next_run_time immediately when interval begins)
    from scheduler_core.services import calculate_next_run
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
    
    # 3. Select and Mark items as RUNNING atomically. (T-SQL for SQL Server)
    placeholders = ", ".join(f":id_{i}" for i in range(len(due_schedule_ids)))
    query_text = f"""
    WITH CTE AS (
        SELECT TOP (:batch_size) id, status, last_run_time
        FROM items
        WHERE active = 1 
          AND schedule_id IN ({placeholders})
          AND status NOT IN ('RUNNING', 'DISABLED')
          AND url IS NOT NULL
          AND TRIM(url) != ''
        ORDER BY 
            CASE WHEN last_run_time IS NULL THEN 0 ELSE 1 END, 
            last_run_time ASC
    )
    UPDATE CTE 
    SET status = 'RUNNING',
        last_run_time = :now
    OUTPUT inserted.id;
    """
    query = text(query_text)
    
    params = {"now": now, "batch_size": batch_size}
    for i, sid in enumerate(due_schedule_ids):
        params[f"id_{i}"] = sid
        
    result = session.execute(query, params).fetchall()
    updated_ids = [row.id for row in result]
    
    # 4. Initialize JobSummary and ItemHistory
    if updated_ids:
        from scheduler_core.models import ItemHistory
        
        job_summary = JobSummary(
            job_id=job_id,
            start_time=now,
            num_of_items=len(updated_ids)
        )
        session.add(job_summary)
        
        # Fetch detailed info with join for script_path
        items_data = session.query(
            Item.id, Item.schedule_id, Item.source_id, Item.url, Item.rate, 
            Item.expression, Item.description, Item.comments, Script.path.label("script_path"),
            Item.name, Item.item_code
        ).outerjoin(Script, Item.script_id == Script.id).filter(Item.id.in_(updated_ids)).all()
        
        items_to_run = []
        for row in items_data:
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
                "item_id": row.id,
                "name": row.name,
                "script_path": row.script_path,
                "expression": row.expression,
                "description": row.description,
                "comments": row.comments,
                "url": row.url,
                "rate": row.rate,
                "item_code": row.item_code,
                "source_id": row.source_id,
                "schedule_id": row.schedule_id
            })

        session.commit()
    else:
        items_to_run = []
        
    return items_to_run

def mark_item_done(session, item_id, job_id, status='DONE'):
    """
    Simulates 'Stored Procedure 2': Marks item with final status and updates ItemHistory.
    """
    from scheduler_core.models import ItemHistory
    
    # 1. Update item status
    session.query(Item).filter(Item.id == item_id).update({"status": status})
    
    # 2. Update ItemHistory
    session.query(ItemHistory).filter_by(
        job_id=job_id,
        item_id=item_id
    ).update({"status": status})
        
    session.commit()
