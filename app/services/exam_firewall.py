from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from app.services.assignment_window import (
    SHA256_PATTERN,
    UTC_TIMESTAMPS_EXAM,
    AssignmentWindow,
    assignment_overlaps_windows,
    require_assignment_lineage,
    require_presented_contains_canonical,
    require_sha256_hex,
    require_utc_timestamps,
)


@dataclass(frozen=True)
class ProtectedInterval:
    interval_id: str
    source_sha256: str
    lineage_source_sha256: frozenset[str]
    start_at: datetime
    end_at: datetime


def parse_utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an ISO-8601 UTC value ending in Z")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be a valid ISO-8601 UTC value") from exc


def parse_protected_interval(payload: object) -> ProtectedInterval:
    if not isinstance(payload, dict):
        raise ValueError("protected interval must be an object")

    interval_id = payload.get("id")
    source_sha256 = payload.get("source_sha256")
    if not isinstance(interval_id, str) or not interval_id:
        raise ValueError("protected interval id is required")
    if not isinstance(source_sha256, str) or not SHA256_PATTERN.fullmatch(source_sha256):
        raise ValueError("protected interval source_sha256 must be 64 lowercase hex characters")
    lineage_payload = payload.get("lineage_source_sha256")
    if not isinstance(lineage_payload, list) or not lineage_payload:
        raise ValueError("protected interval lineage_source_sha256 must be a non-empty list")
    if any(
        not isinstance(item, str) or not SHA256_PATTERN.fullmatch(item)
        for item in lineage_payload
    ):
        raise ValueError("protected interval lineage hashes must be 64 lowercase hex characters")
    if payload.get("lineage_is_transitive_complete") is not True:
        raise ValueError("protected interval lineage must declare transitive completeness")
    if payload.get("training_eligible") is not False:
        raise ValueError("protected interval must be training-ineligible")
    if payload.get("assignment_eligible") is not False:
        raise ValueError("protected interval must be assignment-ineligible")

    start_at = parse_utc_timestamp(payload.get("start_at"))
    end_at = parse_utc_timestamp(payload.get("end_at"))
    if start_at >= end_at:
        raise ValueError("protected interval start_at must precede end_at")

    return ProtectedInterval(
        interval_id=interval_id,
        source_sha256=source_sha256,
        lineage_source_sha256=frozenset({source_sha256, *lineage_payload}),
        start_at=start_at,
        end_at=end_at,
    )


def load_exam_firewall(path: Path) -> tuple[ProtectedInterval, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("exam firewall is unavailable or invalid; assignment must fail closed") from exc

    if payload.get("schema_version") != "factory-vision-exam-firewall-v2":
        raise ValueError("unsupported exam firewall schema; assignment must fail closed")
    if payload.get("fail_closed") is not True:
        raise ValueError("exam firewall must declare fail_closed=true")

    intervals_payload = payload.get("intervals")
    if not isinstance(intervals_payload, list) or not intervals_payload:
        raise ValueError("exam firewall must contain at least one protected interval")

    intervals = tuple(parse_protected_interval(item) for item in intervals_payload)
    if len({item.interval_id for item in intervals}) != len(intervals):
        raise ValueError("exam firewall interval ids must be unique")
    return intervals


def assignment_overlaps_exam(
    intervals: Iterable[ProtectedInterval],
    *,
    source_sha256: str,
    start_at: datetime,
    end_at: datetime,
    lineage_source_sha256: Iterable[str],
    lineage_is_transitive_complete: bool,
    presented_start_at: Optional[datetime] = None,
    presented_end_at: Optional[datetime] = None,
) -> bool:
    require_sha256_hex(
        source_sha256,
        message="assignment source_sha256 must be 64 lowercase hex characters",
    )
    timestamps = [start_at, end_at]
    if presented_start_at is not None:
        timestamps.append(presented_start_at)
    if presented_end_at is not None:
        timestamps.append(presented_end_at)
    require_utc_timestamps(timestamps, message=UTC_TIMESTAMPS_EXAM)
    visible_start_at, visible_end_at = require_presented_contains_canonical(
        start_at=start_at,
        end_at=end_at,
        presented_start_at=presented_start_at,
        presented_end_at=presented_end_at,
    )
    source_hashes = require_assignment_lineage(
        source_sha256=source_sha256,
        lineage_source_sha256=lineage_source_sha256,
        lineage_is_transitive_complete=lineage_is_transitive_complete,
        include_source_in_hashes=True,
    )
    return assignment_overlaps_windows(
        intervals,
        AssignmentWindow(source_hashes, visible_start_at, visible_end_at),
    )
