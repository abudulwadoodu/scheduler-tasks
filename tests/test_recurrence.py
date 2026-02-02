
import unittest
from datetime import datetime, timezone
from app.models import Schedule
from app.services import calculate_next_run
from dateutil.rrule import rrulestr

class TestRecurrence(unittest.TestCase):
    def test_legacy_recurrence(self):
        # Legacy daily interval
        now = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        schedule = Schedule(
            name="Daily Legacy",
            frequency_type="daily",
            interval_value=1,
            rrule=None
        )
        next_run = calculate_next_run(schedule, now)
        self.assertEqual(next_run, datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc))

    def test_rrule_weekly(self):
        # Every Tuesday at 10:00
        start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc) # Wednesday
        rrule = "FREQ=WEEKLY;BYDAY=TU"
        schedule = Schedule(
            name="Weekly RRULE",
            rrule=rrule,
            start_time=start_time
        )
        
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc) # Wednesday noon
        
        # Next run should be Tuesday Jan 7th
        next_run = calculate_next_run(schedule, now)
        self.assertEqual(next_run, datetime(2025, 1, 7, 10, 0, 0, tzinfo=timezone.utc))

    def test_rrule_monthly(self):
        # Monthly on the 1st
        start_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        rrule = "FREQ=MONTHLY;BYMONTHDAY=1"
        schedule = Schedule(
            name="Monthly RRULE",
            rrule=rrule,
            start_time=start_time
        )
        
        now = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run(schedule, now)
        self.assertEqual(next_run, datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc))

if __name__ == "__main__":
    unittest.main()
