# import redis
# import json
# import os
# import time
# from datetime import datetime

# r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# GROUP = "job_logger"
# CONSUMER = "job_logger_1"

# # Create group
# try:
#     r.xgroup_create("job_updates", GROUP, id="0", mkstream=True)
# except redis.exceptions.ResponseError:
#     pass


# def update_job_hash(job_id, fields):
#     key = f"job:{job_id}"

#     # Increment counters dynamically
#     for k, v in fields.items():
#         if k.endswith("_done") or k.endswith("_success") or k.endswith("_failed") or k == "retry_pending":
#             r.hincrby(key, k, int(v))

#     # Update status
#     total = int(r.hget(key, "total") or 0)
#     extracted_success = int(r.hget(key, "extracted_success") or 0)
#     extracted_failed = int(r.hget(key, "extracted_failed") or 0)
#     validated_done = int(r.hget(key, "validated_done") or 0)
#     llm_done = int(r.hget(key, "llm_done") or 0)
#     db_done = int(r.hget(key, "db_done") or 0)
#     retry_pending = int(r.hget(key, "retry_pending") or 0)

  

#     all_extracted = (extracted_success + extracted_failed) == total
#     all_validated = validated_done == extracted_success
#     all_saved = db_done == extracted_success
#     no_retry = (retry_pending == 0)

#     print("all_extracted:", all_extracted)
#     print("all_validated:", all_validated)          
#     print("all_saved:", all_saved)
#     print("no_retry:", no_retry)  

#     if all_extracted and all_validated and all_saved and no_retry:
#         print("key1:", key)
#         print("yes finished")
#         r.hset(key, "status", "completed")
#         r.hset(key, "finished_at", int(time.time()))
#         status = r.hget(key, "status")
#         print("new status:", status)

#     else:
#         r.hset(key, "status", "on_progress")


# def write_job_json(job_id):
#     key = f"job:{job_id}"
#     data = r.hgetall(key)

#     folder = f"./logs/job_{job_id}"
#     os.makedirs(folder, exist_ok=True)

#     path = os.path.join(folder, "job.json")
#     data["updated_at"] = int(time.time())

#     with open(path, "w") as f:
#         json.dump(data, f, indent=2)




# # MAIN LOOP
# while True:
#     messages = r.xreadgroup(GROUP, CONSUMER, {"job_updates": ">"}, count=50, block=2000)

#     if not messages:
#         continue

#     _, entries = messages[0]

#     for msg_id, fields in entries:
#         job_id = fields.pop("job_id")
#         update_job_hash(job_id, fields)
#         write_job_json(job_id)
        
#         r.xack("job_updates", GROUP, msg_id)

import redis
import json
import os
import time
from datetime import datetime

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

GROUP = "job_logger"
CONSUMER = "job_logger_1"

# Create consumer group
try:
    r.xgroup_create("job_updates", GROUP, id="0", mkstream=True)
except redis.exceptions.ResponseError:
    pass

# NEW → Create db_save_queue group only once
try:
    r.xgroup_create("db_save_queue", "db_saver", id="0", mkstream=True)
except redis.exceptions.ResponseError:
    pass


def update_job_hash(job_id, fields):
    key = f"job:{job_id}"

    # Increment counters dynamically
    for k, v in fields.items():
        if k.endswith("_done") or k.endswith("_success") or k.endswith("_failed") or k == "retry_pending":
            r.hincrby(key, k, int(v))

    # Fetch updated fields
    total = int(r.hget(key, "total") or 0)
    extracted_success = int(r.hget(key, "extracted_success") or 0)
    extracted_failed = int(r.hget(key, "extracted_failed") or 0)
    validated_done = int(r.hget(key, "validated_done") or 0)
    llm_done = int(r.hget(key, "llm_done") or 0)
    db_done = int(r.hget(key, "db_done") or 0)
    retry_pending = int(r.hget(key, "retry_pending") or 0)

    # Status conditions
    all_extracted = (extracted_success + extracted_failed) == total
    all_validated = validated_done == extracted_success
    all_saved = db_done == extracted_success
    no_retry = retry_pending == 0

    # Update job status
    if all_extracted and all_validated and all_saved and no_retry:
        r.hset(key, "status", "completed")
        r.hset(key, "completed_at", datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
    else:
        r.hset(key, "status", "on_progress")


def build_job_summary(job_id):
    key = f"job:{job_id}"
    data = r.hgetall(key)
    data["updated_at"] = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
    return data


def send_to_db_agent(job_id, summary):
    """
    Pushes job summary to DB saving agent.
    """
    r.xadd("db_save_queue", {
        "type": "job_summary",
        "job_id": job_id,
        "payload": json.dumps(summary)
    })


# ---- MAIN LOOP ----
while True:
    messages = r.xreadgroup(GROUP, CONSUMER, {"job_updates": ">"}, count=50, block=2000)

    if not messages:
        continue

    _, entries = messages[0]

    for msg_id, fields in entries:
        job_id = fields.pop("job_id")

        # Update Redis state
        update_job_hash(job_id, fields)

        # Build job summary
        summary = build_job_summary(job_id)

        # Send to DB agent
        send_to_db_agent(job_id, summary)

        # # (Optional) Write job.json for debugging only
        # folder = f"./logs/job_{job_id}"
        # os.makedirs(folder, exist_ok=True)
        # with open(os.path.join(folder, "job.json"), "w") as f:
        #     json.dump(summary, f, indent=2)

        # ACK message
        r.xack("job_updates", GROUP, msg_id)
