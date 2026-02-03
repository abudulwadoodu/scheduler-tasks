import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Schedule, Item, Source
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
        next_run_time=now,
        rrule=None
    ),
    Schedule(
        name="RRULE Every Minute",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=MINUTELY;INTERVAL=1"
    ),
    Schedule(
        name="RRULE Every Minute",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=MINUTELY;INTERVAL=1"
    ),
    Schedule(
        name="RRULE Weekly on Tuesday",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=WEEKLY;BYDAY=TU"
    ),
    Schedule(
        name="RRULE Monthly 1st Day",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=MONTHLY;BYMONTHDAY=1"
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
    Schedule(
        name="Complex Monday",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=WEEKLY;BYDAY=MO;BYHOUR=16;BYMINUTE=15,25"
    ),
    Schedule(
        name="Bi-weekly Tuesday",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=WEEKLY;INTERVAL=2;BYDAY=TU;BYHOUR=11;BYMINUTE=0"
    ),
    Schedule(
        name="Monthly 3rd Wed",
        frequency_type=None,
        interval_value=None,
        active=True,
        max_retries=3,
        next_run_time=now,
        start_time=now,
        rrule="FREQ=MONTHLY;BYDAY=3WE"
    ),
]

session.add_all(schedules)
session.commit()

# -------- Sources --------

sources = [
    Source(source_name="Amazon", source_type="Retailer", active=True, created_at=now),
    Source(source_name="Flipkart", source_type="Retailer", active=True, created_at=now),
    Source(source_name="Ebay", source_type="Retailer", active=True, created_at=now),
    Source(source_name="Generic", source_type="Various", active=True, created_at=now),
    Source(source_name="WALMART", source_type="Retailer", active=True, created_at=now),
    Source(source_name="Bigbasket", source_type="Retailer", active=True, created_at=now),
]

session.add_all(sources)
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

    Item(item_code="RRULE001", name="RRULE Test", url="https://example.com/rrule", schedule_id=schedules[1].id, status="PENDING", active=True),
    Item(item_code="RRULE_WEEK", name="Weekly Check", url="https://example.com/weekly", schedule_id=schedules[2].id, status="PENDING", active=True),
    Item(item_code="RRULE_MONTH", name="Monthly Report", url="https://example.com/monthly", schedule_id=schedules[3].id, status="PENDING", active=True),

    Item(item_code="HOUR001", name="GitHub API", url="https://api.github.com", schedule_id=schedules[4].id, status="PENDING", active=True),

    Item(item_code="DAY001", name="StackOverflow", url="https://stackoverflow.com", schedule_id=schedules[5].id, status="PENDING", active=True),

    Item(item_code="WEEK001", name="Python Org", url="https://www.python.org", schedule_id=schedules[6].id, status="PENDING", active=True),

    Item(item_code="MONTH001", name="Wikipedia", url="https://www.wikipedia.org", schedule_id=schedules[7].id, status="PENDING", active=True),

    Item(item_code="QTR001", name="Microsoft", url="https://www.microsoft.com", schedule_id=schedules[8].id, status="PENDING", active=True),

    Item(item_code="YEAR001", name="OpenAI", url="https://www.openai.com", schedule_id=schedules[9].id, status="PENDING", active=True),

    Item(item_code="CMPLX_MON", name="Mon 4:15/4:25", url="https://example.com/mon", schedule_id=schedules[10].id, status="PENDING", active=True),
    Item(item_code="CMPLX_TUE", name="Bi-weekly Tue", url="https://example.com/tue", schedule_id=schedules[11].id, status="PENDING", active=True),
    Item(item_code="CMPLX_WED", name="Monthly 3rd Wed", url="https://example.com/wed", schedule_id=schedules[12].id, status="PENDING", active=True),
    
    # New Mapping Test Items
    Item(item_code="AMZ001", name="Amazon Product", url="https://www.amazon.in/dp/B07PFFMPDB", schedule_id=schedules[0].id, status="PENDING", active=True, item_type="type_1"),
    Item(item_code="FK001", name="Flipkart Product", url="https://www.flipkart.com/p/itme123", schedule_id=schedules[0].id, status="PENDING", active=True, item_type="type_1"),
    
    # New Mapping Test Items (IDs are assigned after Sources are created in populate_mappings, 
    # but here we simulate what the user would do manually)
    # Amazon (ID 1), Flipkart (ID 2), Ebay (ID 3), Walmart (ID 5)
    Item(item_code="AMZ001", name="Amazon Product", url="https://www.amazon.in/dp/B07PFFMPDB", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=1, item_type="type_1"),
    Item(item_code="FK001", name="Flipkart Product", url="https://www.flipkart.com/p/itme123", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=2, item_type="type_1"),
    Item(item_code="EBAY001", name="eBay Collectible", url="https://www.ebay.com/itm/123456", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=3, item_type="type_1"),
    Item(item_code="WMT001", name="Walmart Grocery", url="https://www.walmart.com/ip/111", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=5, item_type="type_1"),
    Item(item_code="WMT002", name="Walmart Electronics", url="https://www.walmart.com/ip/222", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=5, item_type="type_2"),
    Item(item_code="BB001", name="Bigbasket Grocery", url="https://www.bigbasket.com/pd/123", schedule_id=schedules[0].id, status="PENDING", active=True, source_id=6, item_type="type_1"),
]

session.add_all(items)
session.commit()
session.close()

print("Seed data for all frequencies inserted successfully")
