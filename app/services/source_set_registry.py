from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.services.assignment_window import (
    SHA256_PATTERN,
    UTC_TIMESTAMPS_SOURCE_SET,
    AssignmentWindow,
    assignment_overlaps_windows,
    require_assignment_lineage,
    require_presented_contains_canonical,
    require_sha256_hex,
    require_utc_timestamps,
)
from app.services.exam_firewall import (
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
    source_sha256: str,
    lineage_source_sha256: frozenset[str],
    lineage_is_transitive_complete: bool,
    start_at: datetime,
    end_at: datetime,
    presented_start_at: datetime | None = None,
    presented_end_at: datetime | None = None,
    guard_band_seconds: float = 60,
) -> bool:
    require_sha256_hex(
        source_sha256,
        message="assignment source_sha256 must be 64 lowercase hex characters",
    )
    source_hashes = require_assignment_lineage(
        source_sha256=source_sha256,
        lineage_source_sha256=lineage_source_sha256,
        lineage_is_transitive_complete=lineage_is_transitive_complete,
        include_source_in_hashes=True,
    )
    if guard_band_seconds < 0:
        raise ValueError("guard_band_seconds must not be negative")
    timestamps = [start_at, end_at]
    if presented_start_at is not None:
        timestamps.append(presented_start_at)
    if presented_end_at is not None:
        timestamps.append(presented_end_at)
    require_utc_timestamps(timestamps, message=UTC_TIMESTAMPS_SOURCE_SET)
    visible_start_at, visible_end_at = require_presented_contains_canonical(
        start_at=start_at,
        end_at=end_at,
        presented_start_at=presented_start_at,
        presented_end_at=presented_end_at,
    )
    return assignment_overlaps_windows(
        windows,
        AssignmentWindow(source_hashes, visible_start_at, visible_end_at),
        guard=timedelta(seconds=guard_band_seconds),
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
