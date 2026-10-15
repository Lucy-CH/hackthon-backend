from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def next_weekday_arrival() -> datetime:
    """Return 9:30 AM on the next weekday, excluding no public holidays."""
    arrival = datetime.now(ZoneInfo("Asia/Hong_Kong")).replace(
        hour=9,
        minute=30,
        second=0,
        microsecond=0,
    )

    arrival += timedelta(days=1)

    while arrival.weekday() >= 5:
        arrival += timedelta(days=1)

    return arrival