import time

def log_job_update(r, job_id, **fields):
    record = {
        "job_id": job_id,
        "timestamp": str(int(time.time()))
    }

    for k, v in fields.items():
        record[k] = str(v)

    r.xadd("job_updates", record)