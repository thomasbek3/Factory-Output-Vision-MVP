from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-teacher-fusion-v1"
GENERATED_BY = "asymmetric_teacher_fusion_v1"


def build_teacher_fusion_report(
    *,
    teacher_labels_path: Path,
    state_diff_path: Path,
    output_dataset_path: Path | None = None,
) -> dict[str, Any]:
    labels_payload = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    state_payload = json.loads(state_diff_path.read_text(encoding="utf-8"))
    state_by_packet = {str(row["packet_id"]): row for row in state_payload.get("rows") or []}
    decisions: list[dict[str, Any]] = []
    silver_candidates: list[dict[str, Any]] = []
    for label in labels_payload.get("labels") or []:
        packet_id = str(label.get("packet_id") or "")
        state = state_by_packet.get(packet_id, {})
        decision = _fusion_decision(label=label, state=state)
        row = {
            "packet_id": packet_id,
            "window_id": label.get("window_id"),
            "candidate_id": label.get("candidate_id"),
            "verification_decision": label.get("verification_decision"),
            "teacher_output_status": label.get("teacher_output_status"),
            "state_change_detected": state.get("state_change_detected"),
            "reconciliation_status": state.get("reconciliation_status"),
            "fusion_decision": decision,
            "validation_truth_eligible": False,
            "training_candidate": decision == "promote_to_silver_training_candidate",
            "training_eligible": False,
            "promotion_reason": _promotion_reason(decision),
        }
        decisions.append(row)
        if row["training_candidate"]:
            silver_candidates.append(
                {
                    "item_id": f"{packet_id}-silver",
                    "packet_id": packet_id,
                    "window_id": label.get("window_id"),
                    "candidate_id": label.get("candidate_id"),
                    "label_authority_tier": "silver",
                    "source_teacher_label_id": label.get("label_id"),
                    "source_state_diff_status": state.get("reconciliation_status"),
                    "validation_truth_eligible": False,
                    "training_candidate": True,
                    "training_eligible": False,
                    "review_status": "pending_replay_gate",
                }
            )
    dataset = _build_silver_dataset(
        teacher_labels_path=teacher_labels_path,
        state_diff_path=state_diff_path,
        silver_candidates=silver_candidates,
    )
    if output_dataset_path is not None:
        output_dataset_path.parent.mkdir(parents=True, exist_ok=True)
        output_dataset_path.write_text(json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "teacher_labels_path": str(teacher_labels_path),
        "state_diff_path": str(state_diff_path),
        "silver_dataset_path": str(output_dataset_path) if output_dataset_path else None,
        "refuses_validation_truth": True,
        "summary": {
            "label_count": len(decisions),
            "silver_candidate_count": len(silver_candidates),
            "needs_review_count": len([row for row in decisions if row["fusion_decision"] == "needs_review"]),
            "hard_negative_count": len([row for row in decisions if row["fusion_decision"] == "hard_negative_candidate"]),
            "discard_duplicate_count": len([row for row in decisions if row["fusion_decision"] == "discard_duplicate"]),
            "unclear_count": len([row for row in decisions if row["fusion_decision"] == "unclear_more_context_needed"]),
        },
        "decisions": decisions,
        "silver_dataset": dataset,
    }


def write_teacher_fusion_report(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fusion_decision(*, label: dict[str, Any], state: dict[str, Any]) -> str:
    verification = str(label.get("verification_decision") or "unclear")
    reconciliation = str(state.get("reconciliation_status") or "unclear")
    duplicate_risk = str(label.get("duplicate_risk") or "unknown")
    if duplicate_risk == "high":
        return "discard_duplicate"
    if verification == "assert_completed" and reconciliation == "matched_asserted_change":
        return "promote_to_silver_training_candidate"
    if verification == "assert_completed":
        return "needs_review"
    if verification == "refute_completed" and reconciliation == "matched_refuted_no_change":
        return "hard_negative_candidate"
    if verification == "refute_completed":
        return "needs_review"
    if reconciliation == "visible_change_without_teacher_assert":
        return "needs_review"
    return "unclear_more_context_needed"


def _promotion_reason(decision: str) -> str:
    if decision == "promote_to_silver_training_candidate":
        return "teacher_asserted_completed_and_state_diff_detected_change"
    if decision == "hard_negative_candidate":
        return "teacher_refuted_completed_and_state_diff_found_no_change"
    if decision == "needs_review":
        return "teacher_and_state_diff_disagreed_or_partial_evidence"
    if decision == "discard_duplicate":
        return "duplicate_risk_high"
    return "insufficient_evidence"


def _build_silver_dataset(
    *,
    teacher_labels_path: Path,
    state_diff_path: Path,
    silver_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "factory-vision-silver-training-candidates-v1",
        "label_source": "asymmetric_teacher_fusion",
        "teacher_labels_path": str(teacher_labels_path),
        "state_diff_path": str(state_diff_path),
        "validation_truth_eligible": False,
        "training_candidate": bool(silver_candidates),
        "training_eligible": False,
        "requires_blind_replay_gate": True,
        "items": silver_candidates,
    }
