import redis
import time
import json

from utils.job_logger import log_job_update

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

GROUP = "llm_agents"
CONSUMER = "agent1"

# -----------------------------------------------------
# 1️⃣ Create consumer group
# -----------------------------------------------------
try:
    r.xgroup_create("extracted", GROUP, id="0", mkstream=True)
    print("[llm_agent] Consumer group created")
except redis.exceptions.ResponseError as e:
    if "BUSYGROUP" in str(e):
        print("[llm_agent] Group already exists")
    else:
        raise


# -----------------------------------------------------
# 2️⃣ Placeholder LLM processor (you will implement)
# -----------------------------------------------------
def process_with_llm(data: dict):
    """
    Replace this with your actual LLM logic.
    For now we return a dummy output.
    """
    return {
        "summary": f"Processed: {data.get('title', '')}",
        "raw": json.dumps(data)
    }


# -----------------------------------------------------
# 3️⃣ Main worker loop
# -----------------------------------------------------
while True:

    # Try pending entries first
    messages = r.xreadgroup(GROUP, CONSUMER, {"extracted": "0"}, count=10, block=1000)

    if not messages or not messages[0][1]:
        # Read new messages
        messages = r.xreadgroup(GROUP, CONSUMER, {"extracted": ">"}, block=5000)

    if not messages or not messages[0][1]:
        continue

    stream, msgs = messages[0]

    for msg_id, fields in msgs:
        url = fields.get("url")
        job_id = fields.get("job_id")

        print(f"[llm_agent] Processing {url} (job {job_id})")

        try:
            # Process through LLM
            llm_output = process_with_llm(fields)

            # Write to final stream
            r.xadd("llm_processed", {
                "url": url,
                "job_id": job_id,
                **llm_output
            })

            # Update job counters
            if job_id:
                #r.hincrby(f"job:{job_id}", "llm_done", 1)
                log_job_update(r, job_id=job_id, llm_done=1)


        except Exception as e:
            print("[llm_agent] Error:", e)

        # ACK message always
        r.xack("extracted", GROUP, msg_id)

    time.sleep(0.1)
