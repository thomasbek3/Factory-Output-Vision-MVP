from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.exam_firewall import (
    SHA256_PATTERN,
    ProtectedInterval,
    load_exam_firewall,
    parse_utc_timestamp,
)


REQUIRED_SOURCE_SETS = {
    "resolver_calibration",
    "ai_evaluation_holdout",
    "practice",
    "qualification",
}


@dataclass(frozen=True)
class SourceWindow:
    source_set: str
    source_sha256: str
    lineage_source_sha256: frozenset[str]
    start_at: datetime
    end_at: datetime


def _parse_source_window(source_set: str, payload: object) -> SourceWindow:
    if not isinstance(payload, dict):
        raise ValueError(f"{source_set} source window must be an object")
    source_sha256 = payload.get("source_sha256")
    if not isinstance(source_sha256, str) or not SHA256_PATTERN.fullmatch(source_sha256):
        raise ValueError(f"{source_set} source_sha256 must be 64 lowercase hex characters")
    lineage_payload = payload.get("lineage_source_sha256")
    if not isinstance(lineage_payload, list) or not lineage_payload:
        raise ValueError(f"{source_set} lineage_source_sha256 must be a non-empty list")
    if any(
        not isinstance(item, str) or not SHA256_PATTERN.fullmatch(item)
        for item in lineage_payload
    ):
        raise ValueError(f"{source_set} lineage hashes must be 64 lowercase hex characters")
    if payload.get("lineage_is_transitive_complete") is not True:
        raise ValueError(f"{source_set} lineage must declare transitive completeness")
    start_at = parse_utc_timestamp(payload.get("start_at"))
    end_at = parse_utc_timestamp(payload.get("end_at"))
    if start_at >= end_at:
        raise ValueError(f"{source_set} start_at must precede end_at")
    return SourceWindow(
        source_set,
        source_sha256,
        frozenset({source_sha256, *lineage_payload}),
        start_at,
        end_at,
    )


def validate_source_sets(
    payload: object,
    *,
    cross_set_context_seconds: float = 5,
) -> tuple[SourceWindow, ...]:
    if not isinstance(payload, dict):
        raise ValueError("source-set registry must be an object")
    if payload.get("schema_version") != "factory-vision-review-source-sets-v1":
        raise ValueError("unsupported source-set registry schema")
    if payload.get("fail_closed") is not True:
        raise ValueError("source-set registry must declare fail_closed=true")
    if cross_set_context_seconds < 0:
        raise ValueError("cross_set_context_seconds must not be negative")

    sets = payload.get("sets")
    if not isinstance(sets, dict) or set(sets) != REQUIRED_SOURCE_SETS:
        raise ValueError("source-set registry must contain exactly the four required sets")

    windows = tuple(
        _parse_source_window(source_set, item)
        for source_set, items in sets.items()
        if isinstance(items, list)
        for item in items
    )
    if any(not isinstance(items, list) for items in sets.values()):
        raise ValueError("every source set must be a list")

    for index, left in enumerate(windows):
        for right in windows[index + 1 :]:
            if left.lineage_source_sha256.isdisjoint(right.lineage_source_sha256):
                continue
            margin = (
                timedelta(seconds=cross_set_context_seconds)
                if left.source_set != right.source_set
                else timedelta(0)
            )
            if left.start_at < right.end_at + margin and right.start_at < left.end_at + margin:
                raise ValueError(
                    f"source windows in {left.source_set} and {right.source_set} overlap"
                )
    return windows


def validate_source_sets_against_exam(
    windows: tuple[SourceWindow, ...],
    protected_intervals: tuple[ProtectedInterval, ...],
) -> None:
    holdouts = tuple(
        window for window in windows if window.source_set == "ai_evaluation_holdout"
    )
    for protected in protected_intervals:
        matching_holdouts = [
            window
            for window in holdouts
            if not protected.lineage_source_sha256.isdisjoint(window.lineage_source_sha256)
            and window.start_at <= protected.start_at
            and window.end_at >= protected.end_at
        ]
        if not matching_holdouts:
            raise ValueError(
                f"exam interval {protected.interval_id} is not contained in ai_evaluation_holdout"
            )

        for window in windows:
            if window.source_set == "ai_evaluation_holdout":
                continue
            if protected.lineage_source_sha256.isdisjoint(window.lineage_source_sha256):
                continue
            if window.start_at < protected.end_at and protected.start_at < window.end_at:
                raise ValueError(
                    f"{window.source_set} overlaps exam interval {protected.interval_id}"
                )

def assignment_overlaps_protected_source_set(
    windows: tuple[SourceWindow, ...],
    *,
    lineage_source_sha256: frozenset[str],
    lineage_is_transitive_complete: bool,
    start_at: datetime,
    end_at: datetime,
    presented_start_at: datetime | None = None,
    presented_end_at: datetime | None = None,
    guard_band_seconds: float = 60,
) -> bool:
    if not lineage_source_sha256:
        raise ValueError("assignment lineage_source_sha256 must be non-empty")
    if lineage_is_transitive_complete is not True:
        raise ValueError("assignment lineage must declare transitive completeness")
    if any(not SHA256_PATTERN.fullmatch(item) for item in lineage_source_sha256):
        raise ValueError("assignment lineage hashes must be 64 lowercase hex characters")
    if guard_band_seconds < 0:
        raise ValueError("guard_band_seconds must not be negative")
    timestamps = [start_at, end_at]
    if presented_start_at is not None:
        timestamps.append(presented_start_at)
    if presented_end_at is not None:
        timestamps.append(presented_end_at)
    if any(
        value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)
        for value in timestamps
    ):
        raise ValueError("assignment timestamps must be timezone-aware UTC")
    if start_at >= end_at:
        raise ValueError("assignment start_at must precede end_at")
    visible_start_at = presented_start_at or start_at
    visible_end_at = presented_end_at or end_at
    if visible_start_at > start_at or visible_end_at < end_at:
        raise ValueError("presented interval must contain the canonical assignment interval")
    if visible_start_at >= visible_end_at:
        raise ValueError("presented interval start must precede end")

    guard = timedelta(seconds=guard_band_seconds)
    return any(
        not window.lineage_source_sha256.isdisjoint(lineage_source_sha256)
        and visible_start_at < window.end_at + guard
        and window.start_at - guard < visible_end_at
        for window in windows
    )


def load_source_sets(
    path: Path,
    exam_firewall_path: Path,
) -> tuple[SourceWindow, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("source-set registry is unavailable or invalid; operation must fail closed") from exc
    windows = validate_source_sets(payload)
    validate_source_sets_against_exam(
        windows,
        load_exam_firewall(exam_firewall_path),
    )
    return windows
