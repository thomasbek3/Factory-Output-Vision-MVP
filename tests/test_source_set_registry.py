from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.exam_firewall import ProtectedInterval, load_exam_firewall
from app.services.source_set_registry import (
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
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [],
            "practice": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
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
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [],
            "practice": [
                {
                    "source_sha256": "b" * 64,
                    "lineage_source_sha256": ["b" * 64],
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
                    "start_at": "2026-07-25T10:00:00Z",
                    "end_at": "2026-07-25T10:15:00Z"
                }
            ],
            "ai_evaluation_holdout": [
                {
                    "source_sha256": "d" * 64,
                    "lineage_source_sha256": ["a" * 64],
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
        start_at=existing.start_at,
        end_at=existing.end_at,
    )

    with pytest.raises(ValueError, match="not contained"):
        validate_source_sets_against_exam(windows, (unmirrored,))


def test_holdout_missing_from_exam_firewall_fails_closed() -> None:
    windows = list(
        validate_source_sets(
            json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        )
    )
    existing = windows[0]
    windows.append(
        type(existing)(
            source_set="ai_evaluation_holdout",
            source_sha256="f" * 64,
            lineage_source_sha256=frozenset({"f" * 64}),
            start_at=existing.start_at,
            end_at=existing.end_at,
        )
    )

    with pytest.raises(ValueError, match="not contained in the exam firewall"):
        validate_source_sets_against_exam(
            tuple(windows),
            load_exam_firewall(EXAM_FIREWALL_PATH),
        )
