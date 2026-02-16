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

CONSUMER_GROUP = "extractors"

from scheduler_core.db import SessionLocal
from scheduler_core.procedures import pick_items_to_run
from scheduler_core.config import Config

def dispatch_items_to_redis(items):
    """
    Push DB-selected items into Redis Streams
    using existing routing and load-balancing logic.
    """
    for item in items:
        stream = route_stream_for_url(item["url"])
        print(f"Dispatching to {stream}: {item['url']}")
        
        try:
            r.xadd(stream, {
                "url": str(item["url"]),
                "domain": str(extract_domain(item["url"])),
                "job_id": str(item["job_id"]),
                "item_id": str(item["item_id"]),
                "source_id": str(item["source_id"] or ""),
                "item_code": str(item["item_code"] or ""),
                "name": str(item["name"] or ""),
                "expression": str(item["expression"] or ""),
                "description": str(item["description"] or ""),
                "script_path": str(item["script_path"] or ""),
                "attempt": "0",
            })
        except Exception as e:
            print(f"Error dispatching item {item['item_id']} to {stream}: {e}")
            raise e

    return

def process_due_schedules():
    session = SessionLocal()
    try:
        items_to_run = pick_items_to_run(session, batch_size=Config.BATCH_SIZE)
        
        if not items_to_run:
            print("No due items to process.")
            return

        print(f"Items to run response: {items_to_run}")
        print(f"Processing batch of {len(items_to_run)} items.")

        dispatch_items_to_redis(items_to_run)
                
    except Exception as e:
        print(f"Scheduler error: {e}")
    finally:
        session.close()
            

def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def pick_stream():
    idx = r.incr(RR_COUNTER_KEY)
    return URL_STREAMS[(idx - 1) % len(URL_STREAMS)]


def pick_least_loaded_stream():
    loads = {}

    for stream in URL_STREAMS:
        try:
            groups = r.xinfo_groups(stream)
            group = next(g for g in groups if g["name"] == CONSUMER_GROUP)

            pending = group["pending"]
            lag = group.get("lag", 0)

            loads[stream] = pending + lag

        except Exception:
            loads[stream] = 0

    return min(loads, key=loads.get)

def route_stream_for_url(url: str) -> str:
    domain = extract_domain(url)

    stream = r.hget(DOMAIN_STREAM_MAP_KEY, domain)
    if not stream:
        stream = pick_least_loaded_stream()
        r.hset(DOMAIN_STREAM_MAP_KEY, domain, stream)

    return stream


r = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    decode_responses=True
)


# def create_job(urls):
#     job_id = str(uuid.uuid4())
#     #created_at = int(time.time())
#     created_at = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

#     r.hset(f"job:{job_id}", mapping={
#         "id": job_id,
#         "total": len(urls),

#         # extraction counters
#         "extracted_done": 0,
#         "extracted_success": 0,
#         "extracted_failed": 0,

#         # retry tracking
#         "retry_pending": 0,
#         "retry_done": 0,

#         # validator tracking
#         "validated_done": 0,
#         "validated_success": 0,
#         "validated_failed": 0,

#         "db_done": 0,
#         "llm_done": 0,
        
#         "status": "pending",
#         "created_at": created_at,
#         "started_at": "",
#         "completed_at": "",
#     })

   
#     for url in urls:
#         # pushing URLs to a Redis list for reference
#         r.rpush(f"job:{job_id}:urls", url)

#         stream = route_stream_for_url(url)

#         r.xadd(stream, {
#             "url": url,
#             "domain": extract_domain(url),
#             "job_id": job_id,
#             "attempt": 0,
#             "scheduled_attempt": "no"
#         })


#     print(f"[reader] Created Job {job_id} with {len(urls)} URLs")
#     return job_id


# # --- MAIN EXECUTION ---
# df = pd.read_excel("samples.xlsx")
# df = df.rename(columns={"Source\n": "Source"})
# urls = df["URL"].dropna().tolist()


# df["domain_count"] = df.groupby("Source")["Source"].transform("count")

# df_sorted = df.sort_values("domain_count", ascending=False)

# #print(df_sorted.dtypes)

# #print(df_sorted["URL"].tolist())

# job_id = create_job(df_sorted["URL"].dropna().tolist())
# print(f"Job ID: {job_id} queued successfully.")





from apscheduler.schedulers.background import BackgroundScheduler
import time


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_due_schedules, 'interval', seconds=Config.INTERVAL_SECONDS)
    scheduler.start()
    print("Scheduler started...")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
