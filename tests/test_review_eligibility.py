from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.services.exam_firewall import load_exam_firewall, parse_utc_timestamp
from app.services.review_eligibility import review_interval_is_protected


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAM_FIREWALL_PATH = REPO_ROOT / "validation" / "exam" / "exam_firewall_v2.json"
SOURCE_SET_REGISTRY_PATH = (
    REPO_ROOT / "validation" / "review_portal" / "source_sets_v1.json"
)


def test_composed_eligibility_blocks_exam_guard_band() -> None:
    protected = load_exam_firewall(EXAM_FIREWALL_PATH)[0]

    assert review_interval_is_protected(
        exam_firewall_path=EXAM_FIREWALL_PATH,
        source_set_registry_path=SOURCE_SET_REGISTRY_PATH,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=protected.lineage_source_sha256,
        lineage_is_transitive_complete=True,
        start_at=protected.end_at + timedelta(seconds=30),
        end_at=protected.end_at + timedelta(seconds=40),
        presented_start_at=protected.end_at + timedelta(seconds=30),
        presented_end_at=protected.end_at + timedelta(seconds=40),
    )


def test_composed_eligibility_allows_interval_outside_guard_band() -> None:
    protected = load_exam_firewall(EXAM_FIREWALL_PATH)[0]

    assert not review_interval_is_protected(
        exam_firewall_path=EXAM_FIREWALL_PATH,
        source_set_registry_path=SOURCE_SET_REGISTRY_PATH,
        source_sha256=protected.source_sha256,
        lineage_source_sha256=protected.lineage_source_sha256,
        lineage_is_transitive_complete=True,
        start_at=protected.end_at + timedelta(seconds=61),
        end_at=protected.end_at + timedelta(seconds=70),
        presented_start_at=protected.end_at + timedelta(seconds=61),
        presented_end_at=protected.end_at + timedelta(seconds=70),
    )


@pytest.mark.parametrize(
    "source_set",
    ["resolver_calibration", "ai_evaluation_holdout", "practice", "qualification"],
)
def test_composed_eligibility_blocks_every_populated_source_set_and_guard_band(
    tmp_path: Path,
    source_set: str,
) -> None:
    source_hash = {
        "resolver_calibration": "a" * 64,
        "ai_evaluation_holdout": "b" * 64,
        "practice": "c" * 64,
        "qualification": "d" * 64,
    }[source_set]
    registry = json.loads(SOURCE_SET_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["sets"][source_set].append(
        {
            "source_sha256": source_hash,
            "lineage_source_sha256": [source_hash],
            "lineage_is_transitive_complete": True,
            "start_at": "2026-07-25T10:00:00Z",
            "end_at": "2026-07-25T10:01:00Z",
        }
    )
    registry_path = tmp_path / "source_sets.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    protected_end = parse_utc_timestamp("2026-07-25T10:01:00Z")

    for seconds_after in (0, 1, 59):
        start_at = protected_end + timedelta(seconds=seconds_after)
        assert review_interval_is_protected(
            exam_firewall_path=EXAM_FIREWALL_PATH,
            source_set_registry_path=registry_path,
            source_sha256=source_hash,
            lineage_source_sha256=frozenset({source_hash}),
            lineage_is_transitive_complete=True,
            start_at=start_at,
            end_at=start_at + timedelta(seconds=1),
            presented_start_at=start_at,
            presented_end_at=start_at + timedelta(seconds=1),
        )

    outside_start = protected_end + timedelta(seconds=61)
    assert not review_interval_is_protected(
        exam_firewall_path=EXAM_FIREWALL_PATH,
        source_set_registry_path=registry_path,
        source_sha256=source_hash,
        lineage_source_sha256=frozenset({source_hash}),
        lineage_is_transitive_complete=True,
        start_at=outside_start,
        end_at=outside_start + timedelta(seconds=1),
        presented_start_at=outside_start,
        presented_end_at=outside_start + timedelta(seconds=1),
    )


def test_composed_eligibility_allows_unrelated_ordinary_source() -> None:
    start_at = parse_utc_timestamp("2026-07-25T10:00:00Z")
    source_hash = "e" * 64

    assert not review_interval_is_protected(
        exam_firewall_path=EXAM_FIREWALL_PATH,
        source_set_registry_path=SOURCE_SET_REGISTRY_PATH,
        source_sha256=source_hash,
        lineage_source_sha256=frozenset({source_hash}),
        lineage_is_transitive_complete=True,
        start_at=start_at,
        end_at=start_at + timedelta(seconds=1),
        presented_start_at=start_at,
        presented_end_at=start_at + timedelta(seconds=1),
    )


def test_composed_eligibility_matches_source_hash_when_lineage_omits_it(
    tmp_path: Path,
) -> None:
    source_hash = "f" * 64
    registry = json.loads(SOURCE_SET_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["sets"]["practice"].append(
        {
            "source_sha256": source_hash,
            "lineage_source_sha256": [source_hash],
            "lineage_is_transitive_complete": True,
            "start_at": "2026-07-25T10:00:00Z",
            "end_at": "2026-07-25T10:01:00Z",
        }
    )
    registry_path = tmp_path / "source_sets.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    start_at = parse_utc_timestamp("2026-07-25T10:00:10Z")

    assert review_interval_is_protected(
        exam_firewall_path=EXAM_FIREWALL_PATH,
        source_set_registry_path=registry_path,
        source_sha256=source_hash,
        lineage_source_sha256=frozenset({"9" * 64}),
        lineage_is_transitive_complete=True,
        start_at=start_at,
        end_at=start_at + timedelta(seconds=1),
        presented_start_at=start_at,
        presented_end_at=start_at + timedelta(seconds=1),
    )
