from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.services.exam_firewall import load_exam_firewall
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
