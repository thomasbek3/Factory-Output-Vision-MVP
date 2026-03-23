from typing import Any

from app.db.database import get_connection


def log_event(*, event_type: str, state_from: str | None, state_to: str | None, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events (event_type, state_from, state_to, message)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, state_from, state_to, message),
        )
        conn.commit()


def list_events(*, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, event_type, state_from, state_to, message, created_at
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
