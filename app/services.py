from datetime import timedelta
from dateutil.relativedelta import relativedelta

FREQUENCY_MAP = {
    "minute": lambda x: timedelta(minutes=x),
    "hourly": lambda x: timedelta(hours=x),
    "daily": lambda x: timedelta(days=x),
    "weekly": lambda x: timedelta(weeks=x),
    "monthly": lambda x: relativedelta(months=x),
    "quarterly": lambda x: relativedelta(months=3*x),
    "yearly": lambda x: relativedelta(years=x),
}

def calculate_next_run(schedule, now):
    delta_func = FREQUENCY_MAP.get(schedule.frequency_type)
    if not delta_func:
        return now
    return now + delta_func(schedule.interval_value)
