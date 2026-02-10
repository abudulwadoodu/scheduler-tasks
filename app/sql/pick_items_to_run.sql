-- SQL Reference for Stored Procedure: pick_items_to_run
-- This logic encapsulates the selection and marking of items as 'RUNNING'
-- and generates the necessary history and summary records.

-- Note: The following is a conceptual representation as SQLite does not 
-- support multi-statement procedures or complex procedural logic natively.

/*
PROCEDURE pick_items_to_run(p_batch_size INT, p_now DATETIME)
BEGIN
    -- 1. Advance next_run_time for due schedules 
    -- (This part is often kept in application logic if complex rrules are used)
    
    -- 2. Derive next job_id
    SET v_job_id = (SELECT COALESCE(MAX(job_id), 0) + 1 FROM job_summary);

    -- 3. Select and Mark items as RUNNING
    -- Using RETURNING to capture the items for the application
    UPDATE items 
    SET status = 'RUNNING',
        last_run_time = p_now
    WHERE id IN (
        SELECT i.id 
        FROM items i
        JOIN schedule s ON i.schedule_id = s.id
        WHERE i.active = 1 
          AND s.active = 1
          AND s.next_run_time <= p_now
          AND i.status NOT IN ('RUNNING', 'DISABLED')
        ORDER BY i.last_run_time ASC NULLS FIRST
        LIMIT p_batch_size
    )
    RETURNING id;

    -- Note: Application then fetches details with a JOIN on scripts:
    /*
    SELECT i.id as item_id, i.url, i.rate, i.expression, i.description, i.comments, sc.path as script_path
    FROM items i
    LEFT JOIN scripts sc ON i.script_id = sc.id
    WHERE i.id IN (...)
    */

    --  capture the items for history
    -- (Omitted conceptual detail as SQLite handles this in app logic)
END;
*/
