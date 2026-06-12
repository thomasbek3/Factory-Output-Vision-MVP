from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-teacher-loop-benchmark-v1"
GENERATED_BY = "teacher_loop_benchmark_v1"


def build_teacher_loop_benchmark(
    *,
    event_proposals_path: Path,
    teacher_labels_path: Path,
    fusion_report_path: Path,
    min_silver_candidates: int = 1,
) -> dict[str, Any]:
    if min_silver_candidates < 0:
        raise ValueError("min_silver_candidates must be non-negative")
    event_proposals = json.loads(event_proposals_path.read_text(encoding="utf-8"))
    teacher_labels = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    fusion = json.loads(fusion_report_path.read_text(encoding="utf-8"))
    event_count = int((event_proposals.get("summary") or {}).get("event_proposal_count") or 0)
    silver_count = int((fusion.get("summary") or {}).get("silver_candidate_count") or 0)
    needs_review_count = int((fusion.get("summary") or {}).get("needs_review_count") or 0)
    hard_negative_count = int((fusion.get("summary") or {}).get("hard_negative_count") or 0)
    unclear_label_count = len(
        [label for label in teacher_labels.get("labels") or [] if label.get("verification_decision") == "unclear"]
    )
    label_count = len(teacher_labels.get("labels") or [])
    provider = teacher_labels.get("provider") or {}
    no_teacher_baseline = {
        "candidate_count": event_count,
        "training_eligible_count": 0,
        "reason": "raw motion proposals are high-recall candidates only and cannot train or validate by themselves",
    }
    teacher_pipeline = {
        "label_count": label_count,
        "unclear_label_count": unclear_label_count,
        "silver_candidate_count": silver_count,
        "needs_review_count": needs_review_count,
        "hard_negative_count": hard_negative_count,
        "training_eligible_count": silver_count,
    }
    teacher_beats_baseline = silver_count >= min_silver_candidates and silver_count > 0
    status = _status(
        provider=provider,
        label_count=label_count,
        unclear_label_count=unclear_label_count,
        teacher_beats_baseline=teacher_beats_baseline,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "event_proposals_path": str(event_proposals_path),
        "teacher_labels_path": str(teacher_labels_path),
        "fusion_report_path": str(fusion_report_path),
        "refuses_validation_truth": True,
        "training_promotion_requires_blind_replay": True,
        "benchmark_gate": {
            "status": status,
            "teacher_beats_no_teacher_baseline": teacher_beats_baseline,
            "min_silver_candidates": min_silver_candidates,
            "cloud_or_model_calls_made": bool(provider.get("network_calls_made") is True),
        },
        "no_teacher_baseline": no_teacher_baseline,
        "teacher_pipeline": teacher_pipeline,
        "claim_boundary": "benchmark_scaffold_only_not_validation_proof",
    }


def write_teacher_loop_benchmark(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _status(
    *,
    provider: dict[str, Any],
    label_count: int,
    unclear_label_count: int,
    teacher_beats_baseline: bool,
) -> str:
    if label_count > 0 and unclear_label_count == label_count and provider.get("network_calls_made") is False:
        return "needs_real_teacher_or_more_evidence"
    if teacher_beats_baseline:
        return "teacher_pipeline_ready_for_replay_gate"
    return "teacher_pipeline_did_not_beat_baseline"
