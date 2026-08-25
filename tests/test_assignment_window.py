"""Tests for the shared assignment-window overlap predicate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services.assignment_window import (
    AssignmentWindow,
    assignment_overlaps_windows,
    require_assignment_lineage,
    require_presented_contains_canonical,
    require_sha256_hex,
    require_utc_timestamps,
)


@dataclass(frozen=True)
class _Window:
    lineage_source_sha256: frozenset[str]
    start_at: datetime
    end_at: datetime


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_zero_guard_matches_half_open_interval_overlap() -> None:
    protected = _Window(frozenset({"a" * 64}), utc("2026-06-11T22:00:00Z"), utc("2026-06-11T22:01:00Z"))
    touching = AssignmentWindow(
        frozenset({"a" * 64}),
        utc("2026-06-11T22:01:00Z"),
        utc("2026-06-11T22:02:00Z"),
    )
    overlapping = AssignmentWindow(
        frozenset({"a" * 64}),
        utc("2026-06-11T22:00:30Z"),
        utc("2026-06-11T22:01:30Z"),
    )
    assert not assignment_overlaps_windows([protected], touching)
    assert assignment_overlaps_windows([protected], overlapping)


def test_guard_band_blocks_adjacent_assignment() -> None:
    protected = _Window(frozenset({"a" * 64}), utc("2026-06-11T22:00:00Z"), utc("2026-06-11T22:01:00Z"))
    just_outside = AssignmentWindow(
        frozenset({"a" * 64}),
        utc("2026-06-11T22:01:01Z"),
        utc("2026-06-11T22:01:10Z"),
    )
    assert not assignment_overlaps_windows([protected], just_outside)
    assert assignment_overlaps_windows([protected], just_outside, guard=timedelta(seconds=60))


def test_unrelated_hash_never_overlaps() -> None:
    protected = _Window(frozenset({"a" * 64}), utc("2026-06-11T22:00:00Z"), utc("2026-06-11T22:01:00Z"))
    other = AssignmentWindow(
        frozenset({"b" * 64}),
        utc("2026-06-11T22:00:00Z"),
        utc("2026-06-11T22:01:00Z"),
    )
    assert not assignment_overlaps_windows([protected], other, guard=timedelta(seconds=60))


def test_presented_must_contain_canonical() -> None:
    start = utc("2026-06-11T22:00:10Z")
    end = utc("2026-06-11T22:00:20Z")
    with pytest.raises(ValueError, match="presented interval must contain"):
        require_presented_contains_canonical(
            start_at=start,
            end_at=end,
            presented_start_at=utc("2026-06-11T22:00:11Z"),
            presented_end_at=end,
        )


def test_naive_timestamp_fails_closed() -> None:
    naive = datetime(2026, 6, 11, 22, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        require_utc_timestamps([naive], message="assignment timestamps must be timezone-aware UTC")


def test_lineage_must_be_complete_and_nonempty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        require_assignment_lineage(
            source_sha256="a" * 64,
            lineage_source_sha256=[],
            lineage_is_transitive_complete=True,
            include_source_in_hashes=True,
        )
    with pytest.raises(ValueError, match="transitive completeness"):
        require_assignment_lineage(
            source_sha256="a" * 64,
            lineage_source_sha256=["a" * 64],
            lineage_is_transitive_complete=False,
            include_source_in_hashes=True,
        )


def test_source_hash_rejected_when_not_hex() -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        require_sha256_hex("not-a-hash", message="assignment source_sha256 must be 64 lowercase hex characters")
