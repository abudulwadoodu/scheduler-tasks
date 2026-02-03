import redis
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

print("[scheduler] Watching failed retries...")

FAILED_SETS = {
    "failed_urls": "urls",               # extraction retry → send back to "urls"
    "failed_validations": "extracted"    # validation retry → send back to "extracted"
}

while True:
    now = int(time.time())

    for zset_name, stream_name in FAILED_SETS.items():

        # Fetch all ready-to-retry entries
        due_entries = r.zrangebyscore(zset_name, 0, now, withscores=False)

        for entry in due_entries:

            # Entry format must be:  "URL||JOBID"
            try:
                url, job_id = entry.split("||")
            except ValueError:
                print(f"[scheduler] Invalid entry in {zset_name}: {entry}")
                r.zrem(zset_name, entry)
                continue

            print(f"[scheduler] Retrying → {url} (job {job_id}) from {zset_name}")

            # Requeue with attempt = 0
            r.xadd(stream_name, {
                "url": url,
                "job_id": job_id,
                "attempt": 0,
                "scheduled_attempt": "yes"
            })

            # Remove from ZSET
            r.zrem(zset_name, entry)

            # Decrease pending retry count
            #r.hincrby(f"job:{job_id}", "retry_pending", -1)

            # Increase successful retry dequeued count
            r.hincrby(f"job:{job_id}", "retry_done", 1)

    time.sleep(10)  # check every 10 seconds
