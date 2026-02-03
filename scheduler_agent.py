from datetime import datetime 
import redis
import pandas as pd
import time
import uuid
from urllib.parse import urlparse

import yaml

from utils.config import load_config

config = load_config()


EXTRACTOR_REPLICAS = config["pipeline"]["extractor"]["replicas"]
STREAM_PREFIX = config["pipeline"]["extractor"]["stream_prefix"]

URL_STREAMS = [
    f"{STREAM_PREFIX}{i+1}"
    for i in range(EXTRACTOR_REPLICAS)
]

DOMAIN_STREAM_MAP_KEY = "domain_to_stream"
RR_COUNTER_KEY = "stream_rr_counter"

def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def pick_stream():
    idx = r.incr(RR_COUNTER_KEY)
    return URL_STREAMS[(idx - 1) % len(URL_STREAMS)]

def route_stream_for_url(url: str) -> str:
    domain = extract_domain(url)

    stream = r.hget(DOMAIN_STREAM_MAP_KEY, domain)
    if not stream:
        stream = pick_stream()
        r.hset(DOMAIN_STREAM_MAP_KEY, domain, stream)

    return stream

r = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    decode_responses=True
)


info = r.info()
print("[extractor redis info]: version =", info.get("redis_version"))
print("[extractor redis info]: run_id  =", info.get("run_id"))



def create_job(urls):
    job_id = str(uuid.uuid4())
    #created_at = int(time.time())
    created_at = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

    r.hset(f"job:{job_id}", mapping={
        "id": job_id,
        "total": len(urls),

        # extraction counters
        "extracted_done": 0,
        "extracted_success": 0,
        "extracted_failed": 0,

        # retry tracking
        "retry_pending": 0,
        "retry_done": 0,

        # validator tracking
        "validated_done": 0,
        "validated_success": 0,
        "validated_failed": 0,

        "db_done": 0,
        "llm_done": 0,

        # job state
        "status": "pending",
        "created_at": created_at,
        "started_at": "",
        "completed_at": "",
    })

   
    for url in urls:
        # pushing URLs to a Redis list for reference
        r.rpush(f"job:{job_id}:urls", url)

        stream = route_stream_for_url(url)

        r.xadd(stream, {
            "url": url,
            "domain": extract_domain(url),
            "job_id": job_id,
            "attempt": 0,
            "scheduled_attempt": "no"
        })


    print(f"[reader] Created Job {job_id} with {len(urls)} URLs")
    return job_id


# --- MAIN EXECUTION ---
df = pd.read_excel("sample_urls.xlsx")
urls = df["URL"].dropna().tolist()

job_id = create_job(urls)
print(f"Job ID: {job_id} queued successfully.")
