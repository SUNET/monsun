"""Timezone helpers. Storage is always UTC (timestamptz); admins type and read
times in settings.timezone, so naive datetime-local input is interpreted there."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings

LOCAL_TZ = ZoneInfo(settings.timezone)


def local(dt: datetime) -> datetime:
    """Convert a stored datetime to the display timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


def parse_schedule(val: str | None) -> datetime | None:
    """Parse a datetime-local string (display timezone) into a UTC-aware datetime, or None."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)
