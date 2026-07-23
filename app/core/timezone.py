from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from app.core.config import settings
from typing import Optional

APP_TIMEZONE = ZoneInfo(settings.APP_TIMEZONE)

def now_in_app_timezone() -> datetime:
    return datetime.now(APP_TIMEZONE)

def to_app_timezone(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(APP_TIMEZONE)

def to_app_isoformat(value: Optional[datetime]) -> Optional[str]:
    dt = to_app_timezone(value)
    if not dt:
        return None
    return dt.isoformat()

def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=APP_TIMEZONE)
    end = datetime.combine(day, time.max, tzinfo=APP_TIMEZONE)
    return start, end
