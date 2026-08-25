"""Shared assignment-window validation and lineage/time overlap.

Exam firewall and source-set registry used to copy the same prologue and
overlap predicate. Both public functions stay in their original modules so
callers and error strings do not change; they validate in their original
order, then call `assignment_overlaps_windows`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

UTC_TIMESTAMPS_EXAM = "assignment and presented timestamps must be timezone-aware UTC"
UTC_TIMESTAMPS_SOURCE_SET = "assignment timestamps must be timezone-aware UTC"


@dataclass(frozen=True)
class AssignmentWindow:
    source_hashes: frozenset[str]
    visible_start_at: datetime
    visible_end_at: datetime


def require_sha256_hex(value: str, *, message: str) -> None:
    if not SHA256_PATTERN.fullmatch(value):
        raise ValueError(message)


def require_utc_timestamps(
    timestamps: Iterable[datetime],
    *,
    message: str,
) -> None:
    if any(
        value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)
        for value in timestamps
    ):
        raise ValueError(message)


def require_presented_contains_canonical(
    *,
    start_at: datetime,
    end_at: datetime,
    presented_start_at: Optional[datetime],
    presented_end_at: Optional[datetime],
) -> tuple[datetime, datetime]:
    if start_at >= end_at:
        raise ValueError("assignment start_at must precede end_at")
    visible_start_at = presented_start_at or start_at
    visible_end_at = presented_end_at or end_at
    if visible_start_at > start_at or visible_end_at < end_at:
        raise ValueError("presented interval must contain the canonical assignment interval")
    if visible_start_at >= visible_end_at:
        raise ValueError("presented interval start must precede end")
    return visible_start_at, visible_end_at


def require_assignment_lineage(
    *,
    source_sha256: str,
    lineage_source_sha256: Iterable[str],
    lineage_is_transitive_complete: bool,
    include_source_in_hashes: bool,
) -> frozenset[str]:
    lineage_hashes = set(lineage_source_sha256)
    if not lineage_hashes:
        raise ValueError("assignment lineage_source_sha256 must be non-empty")
    if lineage_is_transitive_complete is not True:
        raise ValueError("assignment lineage must declare transitive completeness")
    source_hashes = {source_sha256, *lineage_hashes} if include_source_in_hashes else set(lineage_hashes)
    if any(not SHA256_PATTERN.fullmatch(value) for value in source_hashes):
        raise ValueError("assignment lineage hashes must be 64 lowercase hex characters")
    return frozenset(source_hashes)


def assignment_overlaps_windows(
    windows: Iterable[Any],
    assignment: AssignmentWindow,
    *,
    guard: timedelta = timedelta(0),
) -> bool:
    return any(
        not window.lineage_source_sha256.isdisjoint(assignment.source_hashes)
        and assignment.visible_start_at < window.end_at + guard
        and window.start_at - guard < assignment.visible_end_at
        for window in windows
    )
