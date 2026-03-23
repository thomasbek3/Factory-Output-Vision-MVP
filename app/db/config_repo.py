import json
from typing import Any

from app.db.database import get_connection


DEFAULT_CONFIG: dict[str, Any] = {
    "id": 1,
    "camera_ip": None,
    "camera_username": None,
    "camera_password": None,
    "baseline_rate_per_min": None,
    "stream_profile": None,
    "roi_polygon": None,
    "line": None,
    "operator_zone": {"enabled": False, "polygon": None},
}


def _row_to_config(row: dict[str, Any]) -> dict[str, Any]:
    roi_polygon = None
    roi_raw = row.get("roi_polygon_json")
    if roi_raw:
        roi_polygon = json.loads(roi_raw)

    line = None
    if (
        row.get("line_p1_x") is not None
        and row.get("line_p1_y") is not None
        and row.get("line_p2_x") is not None
        and row.get("line_p2_y") is not None
    ):
        line = {
            "p1": {"x": row.get("line_p1_x"), "y": row.get("line_p1_y")},
            "p2": {"x": row.get("line_p2_x"), "y": row.get("line_p2_y")},
            "direction": row.get("line_direction") or "both",
        }

    operator_polygon = None
    operator_raw = row.get("operator_zone_polygon_json")
    if operator_raw:
        operator_polygon = json.loads(operator_raw)

    return {
        "id": row.get("id", 1),
        "camera_ip": row.get("camera_ip"),
        "camera_username": row.get("camera_username"),
        "camera_password": row.get("camera_password"),
        "baseline_rate_per_min": row.get("baseline_rate_per_min"),
        "stream_profile": row.get("stream_profile"),
        "roi_polygon": roi_polygon,
        "line": line,
        "operator_zone": {
            "enabled": bool(row.get("operator_zone_enabled", 0)),
            "polygon": operator_polygon,
        },
    }


def get_config() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, camera_ip, camera_username, camera_password, baseline_rate_per_min, stream_profile,
                   roi_polygon_json, line_p1_x, line_p1_y, line_p2_x, line_p2_y, line_direction,
                   operator_zone_enabled, operator_zone_polygon_json
            FROM config
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        return DEFAULT_CONFIG.copy()

    return _row_to_config(dict(row))


def update_camera_config(*, camera_ip: str, camera_username: str, camera_password: str, stream_profile: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, camera_ip, camera_username, camera_password, stream_profile)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                camera_ip = excluded.camera_ip,
                camera_username = excluded.camera_username,
                camera_password = excluded.camera_password,
                stream_profile = excluded.stream_profile,
                updated_at = CURRENT_TIMESTAMP
            """,
            (camera_ip, camera_username, camera_password, stream_profile),
        )
        conn.commit()


def update_baseline_rate(*, baseline_rate_per_min: float | None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, baseline_rate_per_min)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                baseline_rate_per_min = excluded.baseline_rate_per_min,
                updated_at = CURRENT_TIMESTAMP
            """,
            (baseline_rate_per_min,),
        )
        conn.commit()


def update_roi_polygon(*, roi_polygon: list[dict[str, float]]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, roi_polygon_json)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                roi_polygon_json = excluded.roi_polygon_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (json.dumps(roi_polygon),),
        )
        conn.commit()


def clear_roi_polygon() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, roi_polygon_json)
            VALUES (1, NULL)
            ON CONFLICT(id) DO UPDATE SET
                roi_polygon_json = NULL,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        conn.commit()


def update_count_line(*, p1: dict[str, float], p2: dict[str, float], direction: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, line_p1_x, line_p1_y, line_p2_x, line_p2_y, line_direction)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                line_p1_x = excluded.line_p1_x,
                line_p1_y = excluded.line_p1_y,
                line_p2_x = excluded.line_p2_x,
                line_p2_y = excluded.line_p2_y,
                line_direction = excluded.line_direction,
                updated_at = CURRENT_TIMESTAMP
            """,
            (p1["x"], p1["y"], p2["x"], p2["y"], direction),
        )
        conn.commit()


def clear_count_line() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, line_p1_x, line_p1_y, line_p2_x, line_p2_y, line_direction)
            VALUES (1, NULL, NULL, NULL, NULL, NULL)
            ON CONFLICT(id) DO UPDATE SET
                line_p1_x = NULL,
                line_p1_y = NULL,
                line_p2_x = NULL,
                line_p2_y = NULL,
                line_direction = NULL,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        conn.commit()


def update_operator_zone(*, enabled: bool, polygon: list[dict[str, float]] | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO config (id, operator_zone_enabled, operator_zone_polygon_json)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                operator_zone_enabled = excluded.operator_zone_enabled,
                operator_zone_polygon_json = excluded.operator_zone_polygon_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (1 if enabled else 0, json.dumps(polygon) if polygon else None),
        )
        conn.commit()
