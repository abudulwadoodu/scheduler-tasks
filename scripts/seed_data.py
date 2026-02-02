import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Schedule, Item
from datetime import datetime, timedelta, timezone

session = SessionLocal()
now = datetime.now(timezone.utc)

# Clean old data (for testing only)
session.query(Item).delete()
session.query(Schedule).delete()
session.commit()

# -------- Schedules --------

schedules = [
    Schedule(
        name="Every 1 Minute",
        frequency_type="minute",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now
    ),
    Schedule(
        name="Every Hour",
        frequency_type="hourly",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=1)
    ),
    Schedule(
        name="Daily",
        frequency_type="daily",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=2)
    ),
    Schedule(
        name="Weekly",
        frequency_type="weekly",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=3)
    ),
    Schedule(
        name="Monthly",
        frequency_type="monthly",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=4)
    ),
    Schedule(
        name="Quarterly",
        frequency_type="quarterly",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=5)
    ),
    Schedule(
        name="Yearly",
        frequency_type="yearly",
        interval_value=1,
        active=True,
        max_retries=3,
        next_run_time=now + timedelta(minutes=6)
    ),
]

session.add_all(schedules)
session.commit()

# -------- Items --------

items = [
    Item(item_code="MIN001", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN002", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN003", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN004", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN005", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN006", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN007", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN008", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),
    Item(item_code="MIN009", name="HttpBin", url="https://httpbin.org/get", schedule_id=schedules[0].id, status="PENDING", active=True),

    Item(item_code="HOUR001", name="GitHub API", url="https://api.github.com", schedule_id=schedules[1].id, status="PENDING", active=True),

    Item(item_code="DAY001", name="StackOverflow", url="https://stackoverflow.com", schedule_id=schedules[2].id, status="PENDING", active=True),

    Item(item_code="WEEK001", name="Python Org", url="https://www.python.org", schedule_id=schedules[3].id, status="PENDING", active=True),

    Item(item_code="MONTH001", name="Wikipedia", url="https://www.wikipedia.org", schedule_id=schedules[4].id, status="PENDING", active=True),

    Item(item_code="QTR001", name="Microsoft", url="https://www.microsoft.com", schedule_id=schedules[5].id, status="PENDING", active=True),

    Item(item_code="YEAR001", name="OpenAI", url="https://www.openai.com", schedule_id=schedules[6].id, status="PENDING", active=True),
]

session.add_all(items)
session.commit()
session.close()

print("Seed data for all frequencies inserted successfully")
