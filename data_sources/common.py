import time
from datetime import date

from dotenv import load_dotenv

load_dotenv()


def current_week_start_date(today=None):
    if today is None:
        today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return date.fromisocalendar(iso_year, iso_week, 1)


def normalize_metrics(week_start_date, source, metrics):
    return [
        {
            "week_start_date": week_start_date.isoformat(),
            "source": source,
            "metric_name": metric_name,
            "value": value,
        }
        for metric_name, value in sorted(metrics.items())
    ]


def retry_with_backoff(func, *args, max_attempts=3, base_delay_seconds=1, sleep_fn=time.sleep, **kwargs):
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception:
            if attempt == max_attempts - 1:
                raise
            sleep_fn(base_delay_seconds * (2 ** attempt))
