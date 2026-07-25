from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.source_set_registry import load_source_sets, validate_source_sets


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "validation" / "review_portal" / "source_sets_v1.json"


def test_tracked_source_sets_are_pairwise_disjoint() -> None:
    windows = load_source_sets(REGISTRY_PATH)

    assert len(windows) == 7
    assert {window.source_set for window in windows} == {"ai_evaluation_holdout"}


def test_cross_set_overlap_fails_closed() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload["sets"]["practice"].append(
        dict(payload["sets"]["ai_evaluation_holdout"][0])
    )

    with pytest.raises(ValueError, match="overlap"):
        validate_source_sets(payload)


def test_adjacent_windows_do_not_overlap() -> None:
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

    assert len(validate_source_sets(payload)) == 2


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
