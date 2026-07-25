from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.exam_firewall import assignment_overlaps_exam, load_exam_firewall


REPO_ROOT = Path(__file__).resolve().parents[1]
FIREWALL_PATH = REPO_ROOT / "validation" / "exam" / "exam_firewall_v2.json"


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_tracked_exam_firewall_loads_and_is_inert() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)

    assert len(intervals) == 7
    assert len({item.source_sha256 for item in intervals}) == 7


def test_assignment_is_blocked_by_hash_and_utc_overlap_not_filename() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    assert assignment_overlaps_exam(
        intervals,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=[protected.source_sha256],
        lineage_is_transitive_complete=True,
        start_at=protected.start_at,
        end_at=protected.end_at,
    )


def test_derived_assignment_is_blocked_by_lineage_hash() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]
    derived_hash = "a" * 64

    assert assignment_overlaps_exam(
        intervals,
        source_sha256=derived_hash,
        lineage_source_sha256=[protected.source_sha256],
        lineage_is_transitive_complete=True,
        start_at=protected.start_at,
        end_at=protected.end_at,
    )


def test_exam_registered_on_derivative_blocks_original_lineage(tmp_path: Path) -> None:
    payload = json.loads(FIREWALL_PATH.read_text(encoding="utf-8"))
    original_hash = payload["intervals"][0]["source_sha256"]
    payload["intervals"][0]["source_sha256"] = "e" * 64
    payload["intervals"][0]["lineage_source_sha256"] = [original_hash]
    derivative_path = tmp_path / "derivative-firewall.json"
    derivative_path.write_text(json.dumps(payload), encoding="utf-8")
    intervals = load_exam_firewall(derivative_path)
    protected = intervals[0]

    assert assignment_overlaps_exam(
        intervals,
        source_sha256=original_hash,
        lineage_source_sha256=[original_hash],
        lineage_is_transitive_complete=True,
        start_at=protected.start_at,
        end_at=protected.end_at,
    )


def test_non_overlapping_interval_is_allowed() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    assert not assignment_overlaps_exam(
        intervals,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=[protected.source_sha256],
        lineage_is_transitive_complete=True,
        start_at=utc("2026-06-11T22:24:49.045000Z"),
        end_at=utc("2026-06-11T22:25:00Z"),
    )


def test_unclipped_visible_context_cannot_leak_adjacent_exam_frames() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    assert assignment_overlaps_exam(
        intervals,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=[protected.source_sha256],
        lineage_is_transitive_complete=True,
        start_at=protected.end_at,
        end_at=utc("2026-06-11T22:25:00Z"),
        presented_start_at=utc("2026-06-11T22:24:44.045000Z"),
        presented_end_at=utc("2026-06-11T22:25:05Z"),
    )


def test_context_clipped_at_exam_boundary_is_eligible() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    assert not assignment_overlaps_exam(
        intervals,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=[protected.source_sha256],
        lineage_is_transitive_complete=True,
        start_at=protected.end_at,
        end_at=utc("2026-06-11T22:25:00Z"),
        presented_start_at=protected.end_at,
        presented_end_at=utc("2026-06-11T22:25:05Z"),
    )


def test_naive_assignment_timestamp_fails_closed() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        assignment_overlaps_exam(
            intervals,
            source_sha256=protected.source_sha256,
            lineage_source_sha256=[protected.source_sha256],
            lineage_is_transitive_complete=True,
            start_at=protected.start_at.replace(tzinfo=None),
            end_at=protected.end_at.replace(tzinfo=None),
        )


def test_assignment_without_lineage_fails_closed() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    with pytest.raises(TypeError, match="lineage_source_sha256"):
        assignment_overlaps_exam(
            intervals,
            source_sha256="a" * 64,
            lineage_is_transitive_complete=True,
            start_at=protected.start_at,
            end_at=protected.end_at,
        )


def test_assignment_with_incomplete_lineage_fails_closed() -> None:
    intervals = load_exam_firewall(FIREWALL_PATH)
    protected = intervals[0]

    with pytest.raises(ValueError, match="transitive completeness"):
        assignment_overlaps_exam(
            intervals,
            source_sha256=protected.source_sha256,
            lineage_source_sha256=[protected.source_sha256],
            lineage_is_transitive_complete=False,
            start_at=protected.start_at,
            end_at=protected.end_at,
        )


def test_invalid_registry_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(FIREWALL_PATH.read_text(encoding="utf-8"))
    del payload["intervals"][0]["source_sha256"]
    invalid_path = tmp_path / "invalid-firewall.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="source_sha256"):
        load_exam_firewall(invalid_path)


def test_registry_without_lineage_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(FIREWALL_PATH.read_text(encoding="utf-8"))
    del payload["intervals"][0]["lineage_source_sha256"]
    invalid_path = tmp_path / "missing-lineage-firewall.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="lineage_source_sha256"):
        load_exam_firewall(invalid_path)
