import redis
import time

from utils.job_logger import log_job_update

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

GROUP = "validators"
CONSUMER = "val1"

# Create consumer group safely (won't error after reset)
try:
    r.xgroup_create("llm_processed", GROUP, id="0", mkstream=True)
except redis.exceptions.ResponseError:
    pass


def validate_data(data):
    """Your existing validation logic goes here."""
    # return True if valid, False otherwise
    return True  # placeholder


while True:
    
    messages = r.xreadgroup(GROUP, CONSUMER, {"llm_processed": "0"}, count=10, block=1000)

    if not messages or not messages[0][1]:
        #print("[validator] reading new messages...")
        messages = r.xreadgroup(GROUP, CONSUMER, {"llm_processed": ">"}, block=5000)

    if not messages or not messages[0][1]:
        continue

    stream, msgs = messages[0]

    print("[validator] messages :", msgs)

    for msg_id, fields in msgs:

        url = fields.get("url")
        job_id = fields.get("job_id")
        attempt = int(fields.get("attempt", 0))

        try:
            ok = validate_data(fields)

            if ok:
                # Successful validation
                if job_id:
                    
                    log_job_update(
                        r,
                        job_id=job_id,
                        validated_done=1,
                        validated_success=1
                    )

                    r.xadd("validated", fields)


        except Exception as e:
            print(f"[validator] Error validating {url}: {e}")

    

            if job_id:
                      
                log_job_update(
                    r,
                    job_id=job_id,
                    validated_done=1,
                    validated_failed=1,
                )
  

        r.xack("llm_processed", GROUP, msg_id)