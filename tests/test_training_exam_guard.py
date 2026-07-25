from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.training_exam_guard import sha256_file, validate_training_row


def write_registries(
    tmp_path: Path,
    *,
    source_sha256: str,
    extra_set: str | None = None,
) -> tuple[Path, Path]:
    exam = {
        "id": "exam-window",
        "source_sha256": source_sha256,
        "lineage_source_sha256": [source_sha256],
        "lineage_is_transitive_complete": True,
        "start_at": "2026-07-25T12:10:00Z",
        "end_at": "2026-07-25T12:11:00Z",
        "training_eligible": False,
        "assignment_eligible": False,
    }
    firewall_path = tmp_path / "exam-firewall.json"
    firewall_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-exam-firewall-v2",
                "fail_closed": True,
                "intervals": [exam],
            }
        ),
        encoding="utf-8",
    )

    sets = {
        "resolver_calibration": [],
        "ai_evaluation_holdout": [
            {
                "source_sha256": source_sha256,
                "lineage_source_sha256": [source_sha256],
                "lineage_is_transitive_complete": True,
                "start_at": "2026-07-25T12:09:00Z",
                "end_at": "2026-07-25T12:12:00Z",
            }
        ],
        "practice": [],
        "qualification": [],
    }
    if extra_set is not None:
        sets[extra_set].append(
            {
                "source_sha256": source_sha256,
                "lineage_source_sha256": [source_sha256],
                "lineage_is_transitive_complete": True,
                "start_at": "2026-07-25T13:00:00Z",
                "end_at": "2026-07-25T13:01:00Z",
            }
        )
    source_sets_path = tmp_path / "source-sets.json"
    source_sets_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-review-source-sets-v1",
                "fail_closed": True,
                "sets": sets,
            }
        ),
        encoding="utf-8",
    )
    return firewall_path, source_sets_path


def training_row(source: Path, *, start_at: str, end_at: str) -> dict:
    source_sha256 = sha256_file(source)
    return {
        "source": str(source),
        "training_eligible": True,
        "source_sha256": source_sha256,
        "lineage_source_sha256": [source_sha256],
        "lineage_is_transitive_complete": True,
        "start_at": start_at,
        "end_at": end_at,
    }


def test_holdout_margin_outside_exam_is_training_ineligible(tmp_path: Path) -> None:
    source = tmp_path / "neutral-source.mkv"
    source.write_bytes(b"holdout source")
    firewall, source_sets = write_registries(
        tmp_path,
        source_sha256=sha256_file(source),
    )

    with pytest.raises(ValueError, match="protected source-set"):
        validate_training_row(
            training_row(
                source,
                start_at="2026-07-25T12:09:05Z",
                end_at="2026-07-25T12:09:20Z",
            ),
            exam_firewall_path=firewall,
            source_set_registry_path=source_sets,
        )


@pytest.mark.parametrize(
    "source_set",
    ["resolver_calibration", "practice", "qualification"],
)
def test_non_exam_protected_sets_are_training_ineligible(
    tmp_path: Path,
    source_set: str,
) -> None:
    source = tmp_path / f"{source_set}.mkv"
    source.write_bytes(source_set.encode("utf-8"))
    firewall, source_sets = write_registries(
        tmp_path,
        source_sha256=sha256_file(source),
        extra_set=source_set,
    )

    with pytest.raises(ValueError, match="protected source-set"):
        validate_training_row(
            training_row(
                source,
                start_at="2026-07-25T13:00:10Z",
                end_at="2026-07-25T13:00:20Z",
            ),
            exam_firewall_path=firewall,
            source_set_registry_path=source_sets,
        )


def test_training_row_outside_all_protected_sets_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "ordinary-source.mkv"
    source.write_bytes(b"ordinary source")
    firewall, source_sets = write_registries(
        tmp_path,
        source_sha256=sha256_file(source),
    )

    validate_training_row(
        training_row(
            source,
            start_at="2026-07-25T14:00:00Z",
            end_at="2026-07-25T14:00:15Z",
        ),
        exam_firewall_path=firewall,
        source_set_registry_path=source_sets,
    )
