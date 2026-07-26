from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.services.exam_firewall import assignment_overlaps_exam, load_exam_firewall
from app.services.source_set_registry import (
    assignment_overlaps_protected_source_set,
    load_source_sets,
)


def review_interval_is_protected(
    *,
    exam_firewall_path: Path,
    source_set_registry_path: Path,
    source_sha256: str,
    lineage_source_sha256: frozenset[str],
    lineage_is_transitive_complete: bool,
    start_at: datetime,
    end_at: datetime,
    presented_start_at: datetime,
    presented_end_at: datetime,
    guard_band_seconds: float = 60,
) -> bool:
    exam_intervals = load_exam_firewall(exam_firewall_path)
    source_windows = load_source_sets(source_set_registry_path, exam_firewall_path)
    return (
        assignment_overlaps_exam(
            exam_intervals,
            source_sha256=source_sha256,
            lineage_source_sha256=lineage_source_sha256,
            lineage_is_transitive_complete=lineage_is_transitive_complete,
            start_at=start_at,
            end_at=end_at,
            presented_start_at=presented_start_at,
            presented_end_at=presented_end_at,
        )
        or assignment_overlaps_protected_source_set(
            source_windows,
            source_sha256=source_sha256,
            lineage_source_sha256=lineage_source_sha256,
            lineage_is_transitive_complete=lineage_is_transitive_complete,
            start_at=start_at,
            end_at=end_at,
            presented_start_at=presented_start_at,
            presented_end_at=presented_end_at,
            guard_band_seconds=guard_band_seconds,
        )
    )
