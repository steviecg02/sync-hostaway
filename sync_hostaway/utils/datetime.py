"""UTC datetime utilities."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Return current UTC time as timezone-aware datetime.

    This function should be used instead of datetime.now() or datetime.utcnow()
    to ensure all timestamps are timezone-aware and stored in UTC.

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> now = utc_now()
        >>> now.tzinfo
        datetime.timezone.utc
        >>> now.tzinfo is not None
        True
    """
    return datetime.now(timezone.utc)
