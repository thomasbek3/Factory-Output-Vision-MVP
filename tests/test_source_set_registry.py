from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.services.exam_firewall import ProtectedInterval, load_exam_firewall
from app.services.source_set_registry import (
    assignment_overlaps_protected_source_set,
    load_source_sets,
    validate_source_sets,
    validate_source_sets_against_exam,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "validation" / "review_portal" / "source_sets_v1.json"
EXAM_FIREWALL_PATH = REPO_ROOT / "validation" / "exam" / "exam_firewall_v2.json"


def test_tracked_source_sets_are_pairwise_disjoint() -> None:
    windows = load_source_sets(REGISTRY_PATH, EXAM_FIREWALL_PATH)

    assert len(windows) == 7
    assert {window.source_set for window in windows} == {"ai_evaluation_holdout"}


def test_cross_set_overlap_fails_closed() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload["sets"]["practice"].append(
        dict(payload["sets"]["ai_evaluation_holdout"][0])
    )

    with pytest.raises(ValueError, match="overlap"):
        validate_source_sets(payload)


def test_duplicate_window_in_same_set_fails_closed() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload["sets"]["ai_evaluation_holdout"].append(
        dict(payload["sets"]["ai_evaluation_holdout"][0])
    )

    with pytest.raises(ValueError, match="overlap"):
        validate_source_sets(payload)


def test_windows_with_five_second_isolation_margin_do_not_overlap() -> None:
    payload = {
        "schema_version": "factory-vision-review-source-sets-v1",
        "fail_closed": True,
        "sets": {
            "resolver_calibration": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [],
            "practice": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:15:05Z",
                    "end_at": "2026-07-25T10:30:00Z"
                }
            ],
            "qualification": []
        }
    }

    assert len(validate_source_sets(payload)) == 2


def test_adjacent_cross_set_windows_fail_context_isolation() -> None:
    payload = {
        "schema_version": "factory-vision-review-source-sets-v1",
        "fail_closed": True,
        "sets": {
            "resolver_calibration": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [],
            "practice": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:15:00Z",
                    "end_at": "2026-07-25T10:30:00Z"
                }
            ],
            "qualification": []
        }
    }

    with pytest.raises(ValueError, match="overlap"):
        validate_source_sets(payload)


def test_reencoded_source_with_shared_lineage_cannot_cross_sets() -> None:
    payload = {
        "schema_version": "factory-vision-review-source-sets-v1",
        "fail_closed": True,
        "sets": {
            "resolver_calibration": [
                {
                    "source_sha256": "c" * 64,
                    "lineage_source_sha256": ["a" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [
                {
                    "source_sha256": "d" * 64,
                    "lineage_source_sha256": ["a" * 64],
                    "lineage_is_transitive_complete": True,
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "practice": [],
            "qualification": []
        }
    }

    with pytest.raises(ValueError, match="overlap"):
        validate_source_sets(payload)


def test_exam_interval_missing_from_holdout_fails_closed() -> None:
    windows = validate_source_sets(
        json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    )
    existing = load_exam_firewall(EXAM_FIREWALL_PATH)[0]
    unmirrored = ProtectedInterval(
        interval_id="exam-source-08",
        source_sha256="e" * 64,
        lineage_source_sha256=frozenset({"e" * 64}),
        start_at=existing.start_at,
        end_at=existing.end_at,
    )

    with pytest.raises(ValueError, match="not contained"):
        validate_source_sets_against_exam(windows, (unmirrored,))


def test_holdout_may_be_wider_than_exam_firewall() -> None:
    windows = list(
        validate_source_sets(
            json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        )
    )
    existing = windows[0]
    windows[0] = type(existing)(
        source_set=existing.source_set,
        source_sha256=existing.source_sha256,
        lineage_source_sha256=existing.lineage_source_sha256,
        start_at=existing.start_at - timedelta(seconds=60),
        end_at=existing.end_at + timedelta(seconds=60),
    )

    validate_source_sets_against_exam(
        tuple(windows),
        load_exam_firewall(EXAM_FIREWALL_PATH),
    )


def test_assignment_inside_holdout_guard_band_is_blocked() -> None:
    windows = load_source_sets(REGISTRY_PATH, EXAM_FIREWALL_PATH)
    holdout = windows[0]

    assert assignment_overlaps_protected_source_set(
        windows,
        source_sha256=holdout.source_sha256,
        lineage_source_sha256=holdout.lineage_source_sha256,
        lineage_is_transitive_complete=True,
        start_at=holdout.end_at + timedelta(seconds=1),
        end_at=holdout.end_at + timedelta(seconds=10),
        guard_band_seconds=60,
    )


def test_assignment_outside_holdout_guard_band_is_allowed() -> None:
    windows = load_source_sets(REGISTRY_PATH, EXAM_FIREWALL_PATH)
    holdout = windows[0]

    assert not assignment_overlaps_protected_source_set(
        windows,
        source_sha256=holdout.source_sha256,
        lineage_source_sha256=holdout.lineage_source_sha256,
        lineage_is_transitive_complete=True,
        start_at=holdout.end_at + timedelta(seconds=61),
        end_at=holdout.end_at + timedelta(seconds=70),
        guard_band_seconds=60,
    )


def test_presented_context_inside_guard_band_is_blocked() -> None:
    windows = load_source_sets(REGISTRY_PATH, EXAM_FIREWALL_PATH)
    holdout = windows[0]

    assert assignment_overlaps_protected_source_set(
        windows,
        source_sha256=holdout.source_sha256,
        lineage_source_sha256=holdout.lineage_source_sha256,
        lineage_is_transitive_complete=True,
        start_at=holdout.end_at + timedelta(seconds=61),
        end_at=holdout.end_at + timedelta(seconds=70),
        presented_start_at=holdout.end_at + timedelta(seconds=59),
        presented_end_at=holdout.end_at + timedelta(seconds=75),
        guard_band_seconds=60,
    )
