from __future__ import annotations

from typing import Any

from app.db.database import get_connection


def insert_health_sample(*, sample: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO health_samples (
                current_state,
                last_frame_age_sec,
                reconnect_attempts_total,
                reader_alive,
                vision_loop_alive,
                person_detect_loop_alive,
                source_kind,
                rolling_rate_per_min,
                baseline_rate_per_min,
                counts_this_minute,
                counts_this_hour,
                last_error_code,
                last_error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample["current_state"],
                sample.get("last_frame_age_sec"),
                sample.get("reconnect_attempts_total", 0),
                1 if sample.get("reader_alive") else 0,
                1 if sample.get("vision_loop_alive") else 0,
                1 if sample.get("person_detect_loop_alive") else 0,
                sample.get("source_kind", "camera"),
                sample.get("rolling_rate_per_min"),
                sample.get("baseline_rate_per_min"),
                sample.get("counts_this_minute", 0),
                sample.get("counts_this_hour", 0),
                sample.get("last_error_code"),
                sample.get("last_error_message"),
            ),
        )
        conn.commit()
