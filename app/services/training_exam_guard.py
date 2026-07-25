from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.services.exam_firewall import (
    SHA256_PATTERN,
    assignment_overlaps_exam,
    load_exam_firewall,
    parse_utc_timestamp,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXAM_FIREWALL_PATH = REPO_ROOT / "validation" / "exam" / "exam_firewall_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_training_row(
    row: dict[str, Any],
    *,
    exam_firewall_path: Path = DEFAULT_EXAM_FIREWALL_PATH,
) -> None:
    if row.get("training_eligible") is False:
        raise ValueError("refusing to label training-ineligible samples")
    if row.get("exam_only") is True or row.get("source_role") == "exam":
        raise ValueError("refusing to label exam window samples")

    source = Path(str(row.get("source", ""))).expanduser()
    if not source.is_file():
        raise ValueError("training row source file is unavailable; operation must fail closed")

    source_sha256 = row.get("source_sha256")
    if not isinstance(source_sha256, str) or not SHA256_PATTERN.fullmatch(source_sha256):
        raise ValueError("training row source_sha256 is required")
    if sha256_file(source) != source_sha256:
        raise ValueError("training row source_sha256 does not match the source file")

    lineage = row.get("lineage_source_sha256")
    if not isinstance(lineage, list) or not lineage:
        raise ValueError("training row lineage_source_sha256 is required")
    if row.get("lineage_is_transitive_complete") is not True:
        raise ValueError("training row lineage must declare transitive completeness")

    start_at = parse_utc_timestamp(row.get("start_at"))
    end_at = parse_utc_timestamp(row.get("end_at"))
    if assignment_overlaps_exam(
        load_exam_firewall(exam_firewall_path),
        source_sha256=source_sha256,
        lineage_source_sha256=lineage,
        lineage_is_transitive_complete=True,
        start_at=start_at,
        end_at=end_at,
        presented_start_at=start_at,
        presented_end_at=end_at,
    ):
        raise ValueError("refusing to label exam window samples")


def validate_training_manifest(
    manifest: dict[str, Any],
    *,
    exam_firewall_path: Path = DEFAULT_EXAM_FIREWALL_PATH,
) -> None:
    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise ValueError("training manifest samples must be a list")
    for row in samples:
        if not isinstance(row, dict):
            raise ValueError("training manifest rows must be objects")
        validate_training_row(row, exam_firewall_path=exam_firewall_path)


def candidate_training_interval(
    *,
    source_start_at: object,
    start_sec: float,
    end_sec: float,
) -> tuple[str, str]:
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError("training candidate offsets must define a positive source interval")
    source_start = parse_utc_timestamp(source_start_at)
    start_at = source_start + timedelta(seconds=start_sec)
    end_at = source_start + timedelta(seconds=end_sec)
    return (
        start_at.isoformat().replace("+00:00", "Z"),
        end_at.isoformat().replace("+00:00", "Z"),
    )
