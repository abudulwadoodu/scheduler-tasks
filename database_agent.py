# import redis
# import os
# import json
# import hashlib
# import time

# from utils.job_logger import log_job_update

# # Function to check if a job is complete
# def check_job_complete(r, job_id):
#     key = f"job:{job_id}"

#     total = int(r.hget(key, "total") or 0)
#     extracted_success = int(r.hget(key, "extracted_success") or 0)
#     extracted_failed = int(r.hget(key, "extracted_failed") or 0)
#     validated_done = int(r.hget(key, "validated_done") or 0)
#     retry_pending = int(r.hget(key, "retry_pending") or 0)
#     db_done = int(r.hget(key, "db_done") or 0)

#     # All urls accounted for?
#     all_extracted = (extracted_success + extracted_failed) == total
#     all_validated = validated_done == extracted_success
#     all_saved = db_done == extracted_success
#     no_retry = retry_pending == 0

#     if (all_extracted and all_validated and all_saved and no_retry):

#         # Only update if not already completed
#         status = r.hget(key, "status")
#         if status != "completed":
#             r.hset(key, "status", "completed")
#             r.hset(key, "completed_at", int(time.time()))

#         return True

#     return False


# r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# GROUP = "db_agents"
# CONSUMER = "db1"


# try:
#     r.xgroup_create("validated", GROUP, id="0", mkstream=True)
#     print("[db_agent] Consumer group created")
# except redis.exceptions.ResponseError as e:
#     if "BUSYGROUP" in str(e):
#         print("[db_agent] Group already exists")
#     else:
#         raise

# def save_to_local(job_id: str, url: str, payload: dict):
#     """
#     Saves the validated data to ./data/job_<job_id>/<hash>.json
#     """

#     # Create folder path
#     root = f"./data/job_{job_id}"
#     os.makedirs(root, exist_ok=True)

#     # Use hash of URL as filename to avoid invalid characters
#     file_id = hashlib.md5(url.encode()).hexdigest()
#     file_path = os.path.join(root, f"{file_id}.json")

#     with open(file_path, "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2)

#     return file_path


# while True:

#     # Read pending messages
#     messages = r.xreadgroup(GROUP, CONSUMER, {"validated": "0"}, count=10, block=1000)

#     if not messages or not messages[0][1]:
#         # Read new messages
#         messages = r.xreadgroup(GROUP, CONSUMER, {"validated": ">"}, block=5000)

#     if not messages or not messages[0][1]:
#         continue

#     stream, entries = messages[0]

#     for msg_id, fields in entries:

#         url = fields.get("url")
#         job_id = fields.get("job_id")

#         print(f"[db_agent] Saving data for {url}")

#         # Save to disk
#         try:
#             file_path = save_to_local(job_id, url, fields)
#             print(f"[db_agent] Saved to {file_path}")

#             # Update job counters
#             if job_id:
#                 # r.hincrby(f"job:{job_id}", "db_done", 1)
#                 log_job_update(r, job_id=job_id, db_done=1)
    
#                 #check_job_complete(r, job_id)

#         except Exception as e:
#             print("[db_agent] Error saving:", e)

#         # Acknowledge message
#         r.xack("validated", GROUP, msg_id)

#     time.sleep(0.1)



import redis
import os
import json
import hashlib
import time

from utils.job_logger import log_job_update

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

GROUP = "db_agents"
CONSUMER = "db1"

# Create consumer groups if needed
streams = ["validated", "db_save_queue"]

for stream in streams:
    try:
        r.xgroup_create(stream, GROUP, id="0", mkstream=True)
        print(f"[db_agent] Consumer group created for {stream}")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[db_agent] Group already exists for {stream}")
        else:
            raise


def save_extracted_to_local(job_id: str, url: str, payload: dict):
    """
    Saves validated data to ./data/job_<job_id>/<hash>.json
    Later: replace with MongoDB insert.
    """
    root = f"./data/job_{job_id}"
    os.makedirs(root, exist_ok=True)

    file_id = hashlib.md5(url.encode()).hexdigest()
    file_path = os.path.join(root, f"{file_id}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return file_path


def save_job_summary_local(job_id, summary):
    """
    Saves job summary to ./logs/job_<job_id>_summary.json
    Later: replace with MongoDB insert.
    """
    folder = "./logs"
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, f"job_{job_id}_summary.json")

    with open(path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[db_agent] Job summary saved: {path}")


def save_log_local(job_id, log_record):
    """
    Save logs to ./db/logs/job_<id>.log file
    Later: replace with MongoDB insert.
    """
    folder = "./db/logs"
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, f"job_{job_id}.log")

    with open(path, "a") as f:
        f.write(json.dumps(log_record) + "\n")

    print(f"[db_agent] Log entry saved for job {job_id}")


# ---------------- MAIN LOOP ---------------- #

while True:

    # -------------------------------------------------
    # 1. HANDLE VALIDATED STREAM (EXTRACTED DATA)
    # -------------------------------------------------
    validated_msgs = r.xreadgroup(GROUP, CONSUMER,
                                  {"validated": ">"}, count=20, block=1000)

    if validated_msgs:
        stream, entries = validated_msgs[0]

        for msg_id, fields in entries:
            job_id = fields.get("job_id")
            url = fields.get("url")

            print(f"[db_agent] Saving extracted data for: {url}")

            try:
                filepath = save_extracted_to_local(job_id, url, fields)
                print(f"[db_agent] Saved to {filepath}")

                # IMPORTANT: db_agent handling only saving
                # Redis counters were already updated by logging_agent
                if job_id:
                    log_job_update(r, job_id=job_id, db_done=1)

            except Exception as e:
                print("[db_agent] Error saving extracted data:", e)

            r.xack("validated", GROUP, msg_id)




    # -------------------------------------------------
    # 2. HANDLE DB_SAVE_QUEUE (JOB SUMMARY + LOGS)
    # -------------------------------------------------
    db_msgs = r.xreadgroup(GROUP, CONSUMER,
                            {"db_save_queue": ">"}, count=50, block=200)

    if db_msgs:
        stream, entries = db_msgs[0]

        for msg_id, fields in entries:
            event_type = fields.get("type")
            job_id = fields.get("job_id")
            payload = json.loads(fields.get("payload"))

            if event_type == "job_summary":
                print(f"[db_agent] Saving job summary for job {job_id}")
                save_job_summary_local(job_id, payload)

            elif event_type == "url_log":
                print(f"[db_agent] Saving URL log for job {job_id}")
                save_log_local(job_id, payload)

            elif event_type == "worker_log":
                print(f"[db_agent] Saving worker log for job {job_id}")
                save_log_local(job_id, payload)

            else:
                print("[db_agent] Unknown event type:", event_type)

            r.xack("db_save_queue", GROUP, msg_id)


    time.sleep(0.1)


