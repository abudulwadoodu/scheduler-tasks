from datetime import datetime
import redis
import importlib
import os
import time
import yaml
from urllib.parse import urlparse

from utils.job_logger import log_job_update

from utils.config import load_config

cfg = load_config()


REDIS_HOST = cfg["redis"]["host"]
REDIS_PORT = cfg["redis"]["port"]

GROUP = cfg["pipeline"]["extractor"]["group"]

STREAM = os.environ["STREAM_NAME"]       # e.g. urls1
CONSUMER = os.environ["CONSUMER_NAME"]   # e.g. ext1


# ----------------------------
# Redis connection
# ----------------------------
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


# ----------------------------
# Ensure consumer group exists
# ----------------------------
try:
    r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    print(f"[extractor:{CONSUMER}] Group created on {STREAM}")
except redis.exceptions.ResponseError as e:
    if "BUSYGROUP" in str(e):
        print(f"[extractor:{CONSUMER}] Group exists on {STREAM}")
    else:
        raise


# ----------------------------
# Domain → extractor module
# ----------------------------
def domain_to_module(domain: str):
    domain = domain.replace("www.", "")
    return domain.replace(".", "_")


def load_extractor(domain: str):
    module_name = domain_to_module(domain)
    try:
        module = importlib.import_module(f"extractors.{module_name}")
        return module.extract
    except ModuleNotFoundError:
        print(f"[extractor:{CONSUMER}] No extractor for {domain}")
        return None


# ----------------------------
# Main loop
# ----------------------------
while True:
    # 1️⃣ Drain pending messages first (crash recovery)
    messages = r.xreadgroup(
        GROUP,
        CONSUMER,
        {STREAM: "0"},
        count=10,
        block=1000
    )

    # 2️⃣ If no pending, read new messages
    if not messages or not messages[0][1]:
        messages = r.xreadgroup(
            GROUP,
            CONSUMER,
            {STREAM: ">"},
            block=5000
        )

    if not messages or not messages[0][1]:
        continue

    _, msgs = messages[0]

    for msg_id, fields in msgs:
        url = fields["url"]
        job_id = fields.get("job_id")
        attempt = int(fields.get("attempt", 0))
        scheduled_attempt = fields.get("scheduled_attempt", "no")
        domain = urlparse(url).netloc

        extractor_func = load_extractor(domain)

        # mark job started
        if job_id and r.hget(f"job:{job_id}", "status") == "pending":
            r.hset(f"job:{job_id}", mapping={
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        try:
            if extractor_func:
                data = extractor_func(url)
                safe_data = {k: "" if v is None else str(v) for k, v in data.items()}

                r.xadd("extracted", {
                    "url": url,
                    "job_id": job_id,
                    **safe_data
                })

                if job_id:
                    log_job_update(
                        r,
                        job_id=job_id,
                        extracted_done=1,
                        extracted_success=1
                    )
            else:
                r.xadd("extracted", {
                    "url": url,
                    "job_id": job_id,
                    "error": "Extractor not found"
                })

                if job_id:
                    log_job_update(
                        r,
                        job_id=job_id,
                        extracted_done=1,
                        extracted_failed=1
                    )

        except Exception as e:
            print(f"[extractor:{CONSUMER}] Error on {url}: {e}")

            if attempt < 1:
                r.xadd(STREAM, {
                    "url": url,
                    "job_id": job_id,
                    "attempt": attempt + 1,
                    "scheduled_attempt": scheduled_attempt
                })
            else:
                retry_time = int(time.time()) + 60
                r.zadd("failed_urls", {f"{url}||{job_id}": retry_time})

        # ✅ ACK exactly once
        r.xack(STREAM, GROUP, msg_id)
