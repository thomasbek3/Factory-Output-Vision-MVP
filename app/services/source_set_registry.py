from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.exam_firewall import SHA256_PATTERN, parse_utc_timestamp


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


def validate_source_sets(payload: object) -> tuple[SourceWindow, ...]:
    if not isinstance(payload, dict):
        raise ValueError("source-set registry must be an object")
    if payload.get("schema_version") != "factory-vision-review-source-sets-v1":
        raise ValueError("unsupported source-set registry schema")
    if payload.get("fail_closed") is not True:
        raise ValueError("source-set registry must declare fail_closed=true")

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
            if (
                left.source_set == right.source_set
                or left.lineage_source_sha256.isdisjoint(right.lineage_source_sha256)
            ):
                continue
            if left.start_at < right.end_at and right.start_at < left.end_at:
                raise ValueError(
                    f"source sets {left.source_set} and {right.source_set} overlap"
                )
    return windows


def load_source_sets(path: Path) -> tuple[SourceWindow, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("source-set registry is unavailable or invalid; operation must fail closed") from exc
    return validate_source_sets(payload)
