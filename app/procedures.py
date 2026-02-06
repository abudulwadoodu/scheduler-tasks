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
    
    for sched in due_schedules:
        # Check if we should reset items to PENDING for a new cycle
        count_not_done = session.query(Item).filter(
            Item.schedule_id == sched.id,
            Item.active == True,
            Item.status.in_(['PENDING', 'RUNNING'])
        ).count()
        
        if count_not_done == 0:
            session.query(Item).filter(
                Item.schedule_id == sched.id,
                Item.active == True
            ).update({"status": "PENDING"})
        
        # Advance schedule (only if last_run_time hasn't been updated to 'now' yet)
        if sched.last_run_time != now:
            sched.last_run_time = now
            sched.next_run_time = calculate_next_run(sched, now)
    
    session.commit()

    # 2. Derive next job_id
    last_job_id = session.query(func.max(JobSummary.job_id)).scalar() or 0
    job_id = last_job_id + 1
    
    # 3. Select and Mark items as RUNNING atomically.
    # Requirement: status != 'RUNNING', active = true
    # We prioritize PENDING items if they exist, but requirement says status != 'RUNNING'.
    # To avoid re-running DONE items in the same interval, we typically pick PENDING.
    # But we just reset them to PENDING above, so picking PENDING is correct.
    
    query = text("""
    UPDATE items 
    SET status = 'RUNNING',
        last_run_time = :now
    WHERE id IN (
        SELECT i.id 
        FROM items i
        JOIN schedule s ON i.schedule_id = s.id
        WHERE i.active = 1 
          AND i.status = 'PENDING'
        ORDER BY i.last_run_time ASC NULLS FIRST
        LIMIT :batch_size
    )
    RETURNING id, schedule_id, source_id, item_code, name, url;
    """)
    
    result = session.execute(query, {"now": now, "batch_size": batch_size}).fetchall()
    
    items_to_run = []
    for row in result:
        items_to_run.append({
            "job_id": job_id,
            "id": row.id,
            "schedule_id": row.schedule_id,
            "source_id": row.source_id,
            "item_code": row.item_code,
            "name": row.name,
            "url": row.url
        })

    session.commit()
    return items_to_run

def mark_item_done(session, item_id, job_id, schedule_id, source_id):
    """
    Simulates 'Stored Procedure 2': Marks item as DONE and updates JobSummary.
    """
    # 1. Update item status
    session.query(Item).filter(Item.id == item_id).update({"status": "DONE"})
    
    # 2. Update JobSummary (Incremental Aggregation)
    summary = session.query(JobSummary).filter_by(
        job_id=job_id,
        schedule_id=schedule_id,
        source_id=source_id
    ).first()
    
    if not summary:
        summary = JobSummary(
            job_id=job_id,
            schedule_id=schedule_id,
            source_id=source_id,
            item_count=1
        )
        session.add(summary)
    else:
        summary.item_count += 1
        
    session.commit()
