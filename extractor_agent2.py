from datetime import datetime
import redis
import importlib
from urllib.parse import urlparse
import time

from utils.job_logger import log_job_update

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

GROUP = "extractors"
CONSUMER = "ext2"

try:
    r.xgroup_create("urls2", GROUP, id="0", mkstream=True)
    print("[extractor] Consumer group created")
except redis.exceptions.ResponseError as e:
    if "BUSYGROUP" in str(e):
        print("[extractor] Group already exists")
    else:
        raise

def domain_to_module(domain: str):
    domain = domain.replace("www.", "")
    return domain.replace(".", "_")

def load_extractor(domain: str):
    module_name = domain_to_module(domain)
    full_path = f"extractors.{module_name}"
    try:
        module = importlib.import_module(full_path)
        return module.extract
    except ModuleNotFoundError:
        print(f"[extractor] No extractor module found for domain: {domain}")
        return None

while True:
    
    # --- Try to read pending messages first ---
    messages = r.xreadgroup(GROUP, CONSUMER, {"urls2": "0"}, count=10, block=1000)
    #print('[extractor] Pending messages fetched:', messages)

    if not messages or not messages[0][1]:
        #print("[extractor] reading new messages...")
            messages = r.xreadgroup(GROUP, CONSUMER, {"urls2": ">"}, block=5000)


    if not messages or not messages[0][1]:
        continue

    stream, msgs = messages[0]

    print("[extractor] messages :", msgs)

    for msg_id, fields in msgs:

        url = fields["url"]
        job_id = fields.get("job_id")
        attempt = int(fields.get("attempt", 0))
        scheduled_attempt = fields.get("scheduled_attempt", "no")
        domain = urlparse(url).netloc
   
        extractor_func = load_extractor(domain)

        # Mark job started
        if job_id and r.hget(f"job:{job_id}", "status") == "pending":
            r.hset(f"job:{job_id}", "status", "running")
            r.hset(f"job:{job_id}", "started_at", datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))

        try:
            # SUCCESS CASE
            if extractor_func:
                data = extractor_func(url)
                safe_data = {k: "" if v is None else str(v) for k, v in data.items()}

                r.xadd("extracted", {"url": url, "job_id": job_id, **safe_data})

                if job_id:
                    # r.hincrby(f"job:{job_id}", "extracted_done", 1)
                    # r.hincrby(f"job:{job_id}", "extracted_success", 1)
                    log_job_update( r,
                                    job_id=job_id,
                                    extracted_done=1,
                                    extracted_success=1
                                    )

                    

            else:
                # extractor missing
                r.xadd("extracted", {
                    "url": url,
                    "job_id": job_id,
                    "title": "N/A",
                    "error": "Extractor not found"
                })

                if job_id:
                    # r.hincrby(f"job:{job_id}", "extracted_done", 1)
                    # r.hincrby(f"job:{job_id}", "extracted_failed", 1)

                    log_job_update(
                                r,
                                job_id=job_id,
                                extracted_done=1,
                                extracted_failed=1
                            )


        except Exception as e:
            print(f"[extractor] Error on {url}: {e}")

            # --- RETRY LOGIC UPDATE ---
            if attempt < 1:
                print(f"[extractor] Retrying {url}, attempt {attempt + 1}/2")

                # schedule next retry
                r.xadd("urls1", {
                    "url": url,
                    "job_id": job_id,
                    "attempt": attempt + 1,
                    "scheduled_attempt": scheduled_attempt
                })


            else:
                if scheduled_attempt == "yes":
                    print(f"[extractor] Final scheduled attempt failed for {url} → discarding")
                    
                    # consume the last retry pending
                    if job_id:
                        # r.hincrby(f"job:{job_id}", "extracted_failed", 1)
                        # r.hincrby(f"job:{job_id}", "retry_pending", -1)
                        # r.hincrby(f"job:{job_id}", "extracted_done", 1)

                        log_job_update(
                            r,
                            job_id=job_id,
                            retry_pending=-1,
                            extracted_failed=1,
                            extracted_done=1
                        )

   

                    r.xack("urls2", GROUP, msg_id)
                    
                else:

                    # FINAL FAILURE
                    print(f"[extractor] Failed after max retries → pushing to failed ZSET")

                    # consume the last retry pending
                    if job_id:
                        # r.hincrby(f"job:{job_id}", "retry_pending", 1)
                        log_job_update(
                            r,
                            job_id=job_id,
                            retry_pending=1
                        )

                    retry_time = int(time.time()) + 60
                    failed_entry = f"{url}||{job_id}"
                    r.zadd("failed_urls", {failed_entry: retry_time})
           
        # ACK the message
        r.xack("urls2", GROUP, msg_id)
