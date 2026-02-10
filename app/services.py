from datetime import timedelta
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrulestr

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
    if schedule.rrule:
        try:
            # Use start_time as dtstart if provided
            rule = rrulestr(schedule.rrule, dtstart=schedule.start_time)
            
            # rrule processing is often naive-safe. If start_time is aware, rule is aware.
            # But if rule ends up naive (e.g. from string), comparing with aware 'now' fails.
            # Safest: Convert now to compatible naive/aware
            check_time = now
            if schedule.start_time and schedule.start_time.tzinfo is None and now.tzinfo:
                 check_time = now.replace(tzinfo=None)
            elif rule._dtstart.tzinfo is None and now.tzinfo:
                 check_time = now.replace(tzinfo=None)

            next_run = rule.after(check_time)
            
            if next_run:
                # Ensure next_run has the same timezone as now if it's currently naive
                if next_run.tzinfo is None and now.tzinfo:
                     next_run = next_run.replace(tzinfo=now.tzinfo)
                return next_run
        except Exception as e:
            print(f"Error calculating RRULE for schedule {schedule.name}: {e}")
            
    delta_func = FREQUENCY_MAP.get(schedule.frequency_type)
    if not delta_func:
        return now
    return now + delta_func(schedule.interval_value)
