from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ProtectedInterval:
    interval_id: str
    source_sha256: str
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
    lineage_source_sha256: Iterable[str] = (),
    visible_context_seconds: float = 0,
) -> bool:
    if not SHA256_PATTERN.fullmatch(source_sha256):
        raise ValueError("assignment source_sha256 must be 64 lowercase hex characters")
    if start_at >= end_at:
        raise ValueError("assignment start_at must precede end_at")
    if visible_context_seconds < 0:
        raise ValueError("visible_context_seconds must not be negative")

    source_hashes = {source_sha256, *lineage_source_sha256}
    if any(not SHA256_PATTERN.fullmatch(value) for value in source_hashes):
        raise ValueError("assignment lineage hashes must be 64 lowercase hex characters")

    visible_start_at = start_at - timedelta(seconds=visible_context_seconds)
    visible_end_at = end_at + timedelta(seconds=visible_context_seconds)

    return any(
        protected.source_sha256 in source_hashes
        and visible_start_at < protected.end_at
        and protected.start_at < visible_end_at
        for protected in intervals
    )
