# # retry_scheduler.py

# import redis
# import time

# r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# print("[scheduler] Watching failed URLs...")

# while True:

#     now = int(time.time())

#     # Fetch all items whose retry time <= now
#     due_urls = r.zrangebyscore("failed_urls", 0, now)

#     for url in due_urls:
#         print(f"[scheduler] Retrying → {url}")

#         # Requeue with attempt = 0
#         r.xadd("urls", {"url": url, "attempt": 0})

#         # Remove from ZSET
#         r.zrem("failed_urls", url)

#     time.sleep(10)  # check every 10 sec

# retry_scheduler.py

import redis
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

print("[scheduler] Watching failed URLs...")

while True:

    now = int(time.time())

    # Fetch all items whose retry time <= now
    due_entries = r.zrangebyscore("failed_urls", 0, now, withscores=False)

    for entry in due_entries:
        # entry format = "URL|JOBID"
        try:
            url, job_id = entry.split("||")
        except ValueError:
            print("[scheduler] ERROR: Invalid failed_urls entry:", entry)
            r.zrem("failed_urls", entry)
            continue

        print(f"[scheduler] Retrying → {url} (job {job_id})")

        # Requeue with attempt = 0
        r.xadd("urls", {
            "url": url,
            "job_id": job_id,
            "attempt": 0
        })

        # Remove from ZSET
        r.zrem("failed_urls", entry)

        # Reduce pending retry count
        r.hincrby(f"job:{job_id}", "retry_pending", -1)

        # Increase retry_dequeued count
        r.hincrby(f"job:{job_id}", "retry_done", 1)

    time.sleep(10)  # check every 10 sec
