from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.database import get_connection


SEGMENT_COLUMNS = (
    "station_id",
    "segment_id",
    "path",
    "file_size_bytes",
    "sha256",
    "source_uri_hash",
    "start_wall_ts",
    "end_wall_ts",
    "duration_sec",
    "codec",
    "container",
    "width",
    "height",
    "fps_estimate",
    "decode_ok",
    "frame_gaps_json",
    "privacy_mode",
    "pinned_reason",
    "probe_error",
)


def upsert_segment_manifest(*, manifest: dict[str, Any]) -> int:
    """Persist recorder manifest rows for lookup without changing retention authority."""
    station_id = str(manifest["station_id"])
    rows = list(manifest.get("segments") or [])
    with get_connection() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO recorded_segments (
                    station_id,
                    segment_id,
                    path,
                    file_size_bytes,
                    sha256,
                    source_uri_hash,
                    start_wall_ts,
                    end_wall_ts,
                    duration_sec,
                    codec,
                    container,
                    width,
                    height,
                    fps_estimate,
                    decode_ok,
                    frame_gaps_json,
                    privacy_mode,
                    pinned_reason,
                    probe_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_id, segment_id) DO UPDATE SET
                    path = excluded.path,
                    file_size_bytes = excluded.file_size_bytes,
                    sha256 = excluded.sha256,
                    source_uri_hash = excluded.source_uri_hash,
                    start_wall_ts = excluded.start_wall_ts,
                    end_wall_ts = excluded.end_wall_ts,
                    duration_sec = excluded.duration_sec,
                    codec = excluded.codec,
                    container = excluded.container,
                    width = excluded.width,
                    height = excluded.height,
                    fps_estimate = excluded.fps_estimate,
                    decode_ok = excluded.decode_ok,
                    frame_gaps_json = excluded.frame_gaps_json,
                    privacy_mode = excluded.privacy_mode,
                    pinned_reason = COALESCE(recorded_segments.pinned_reason, excluded.pinned_reason),
                    probe_error = excluded.probe_error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                _row_values(row, station_id=station_id),
            )
        conn.commit()
    return len(rows)


def list_recorded_segments(*, station_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {", ".join(SEGMENT_COLUMNS)}
            FROM recorded_segments
            WHERE station_id = ?
            ORDER BY COALESCE(start_wall_ts, ''), path
            """,
            (station_id,),
        ).fetchall()
    return [_db_row_to_segment(dict(row)) for row in rows]


def pin_recorded_segment(*, station_id: str, segment_id: str, reason: str) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT path
            FROM recorded_segments
            WHERE station_id = ? AND segment_id = ?
            """,
            (station_id, segment_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown segment_id for station {station_id}: {segment_id}")
        result = conn.execute(
            """
            UPDATE recorded_segments
            SET pinned_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE station_id = ? AND segment_id = ?
            """,
            (reason, station_id, segment_id),
        )
        conn.commit()
    if result.rowcount == 0:
        raise ValueError(f"unknown segment_id for station {station_id}: {segment_id}")
    _pin_manifest_segment(segment_path=Path(str(row["path"])), segment_id=segment_id, reason=reason)


def _row_values(row: dict[str, Any], *, station_id: str) -> tuple[Any, ...]:
    return (
        station_id,
        str(row["segment_id"]),
        str(row["path"]),
        int(row["file_size_bytes"]),
        str(row["sha256"]),
        str(row["source_uri_hash"]),
        row.get("start_wall_ts"),
        row.get("end_wall_ts"),
        row.get("duration_sec"),
        row.get("codec"),
        str(row["container"]),
        row.get("width"),
        row.get("height"),
        row.get("fps_estimate"),
        1 if row.get("decode_ok") else 0,
        json.dumps(row.get("frame_gaps") or []),
        str(row["privacy_mode"]),
        row.get("pinned_reason"),
        row.get("probe_error"),
    )


def _db_row_to_segment(row: dict[str, Any]) -> dict[str, Any]:
    row["decode_ok"] = bool(row["decode_ok"])
    row["frame_gaps"] = json.loads(row.pop("frame_gaps_json") or "[]")
    return row


def _pin_manifest_segment(*, segment_path: Path, segment_id: str, reason: str) -> None:
    manifest_path = segment_path.parent.parent / "segment_manifest.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = False
    for row in payload.get("segments") or []:
        if row.get("segment_id") == segment_id or str(row.get("path")) == str(segment_path):
            row["pinned_reason"] = reason
            changed = True
    if not changed:
        return
    payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
