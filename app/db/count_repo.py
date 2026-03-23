from __future__ import annotations

from datetime import datetime

from app.db.database import get_connection


def _minute_bucket(timestamp: datetime) -> str:
    return timestamp.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def _hour_bucket(timestamp: datetime) -> str:
    return timestamp.replace(minute=0, second=0, microsecond=0).isoformat(timespec="hours")


def record_count_event(*, timestamp: datetime, count_source: str = "vision", increment: int = 1) -> None:
    minute_bucket = _minute_bucket(timestamp)
    hour_bucket = _hour_bucket(timestamp)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO counts_minute (bucket_start, count_source, count_value)
            VALUES (?, ?, ?)
            ON CONFLICT(bucket_start, count_source) DO UPDATE SET
                count_value = count_value + excluded.count_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (minute_bucket, count_source, increment),
        )
        conn.execute(
            """
            INSERT INTO counts_hour (bucket_start, count_source, count_value)
            VALUES (?, ?, ?)
            ON CONFLICT(bucket_start, count_source) DO UPDATE SET
                count_value = count_value + excluded.count_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (hour_bucket, count_source, increment),
        )
        conn.commit()


def clear_count_history() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM counts_minute")
        conn.execute("DELETE FROM counts_hour")
        conn.commit()
