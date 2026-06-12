from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-periodic-audit-v1"
DISPUTE_STATUSES = {"worker_only", "static_stack", "unclear"}
RETRAINING_STATUSES = {"countable", "completed", "worker_only", "static_stack", "unclear"}


def build_periodic_audit_report(
    *,
    observed_events_path: Path,
    teacher_labels_path: Path,
    output_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    observed = json.loads(observed_events_path.read_text(encoding="utf-8"))
    teacher = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    labels = list(teacher.get("labels") or [])
    runtime_total = _runtime_total_from_observed(observed)
    disputes = [_dispute_from_label(label) for label in labels if str(label.get("teacher_output_status")) in DISPUTE_STATUSES]
    retraining_triggers = [
        _retraining_trigger_from_label(label)
        for label in labels
        if str(label.get("teacher_output_status")) in RETRAINING_STATUSES
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": round(time.time(), 3),
        "observed_events_path": str(observed_events_path),
        "teacher_labels_path": str(teacher_labels_path),
        "runtime_total_before_audit": runtime_total,
        "runtime_total_after_audit": runtime_total,
        "runtime_total_mutation_allowed": False,
        "count_authority": "existing_yolo_event_runtime_only",
        "teacher_labels_used_as_truth": False,
        "disputes": disputes,
        "retraining_triggers": retraining_triggers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _runtime_total_from_observed(observed: dict[str, Any]) -> int:
    events = list(observed.get("events") or [])
    if not events:
        return int(observed.get("observed_event_count") or 0)
    last = max(events, key=lambda row: float(row.get("event_ts") or 0.0))
    return int(last.get("runtime_total_after_event") or len(events))


def _dispute_from_label(label: dict[str, Any]) -> dict[str, Any]:
    return {
        "dispute_id": f"{label.get('label_id')}-dispute",
        "window_id": label.get("window_id"),
        "teacher_output_status": label.get("teacher_output_status"),
        "review_status": "needs_review",
        "reason": "audit_teacher_does_not_confirm_countable_output",
        "mutates_runtime_total": False,
    }


def _retraining_trigger_from_label(label: dict[str, Any]) -> dict[str, Any]:
    status = str(label.get("teacher_output_status") or "unclear")
    if status in {"worker_only", "static_stack", "unclear"}:
        trigger_type = "hard_negative_candidate"
    else:
        trigger_type = "positive_candidate"
    return {
        "trigger_id": f"{label.get('label_id')}-retraining",
        "window_id": label.get("window_id"),
        "trigger_type": trigger_type,
        "label_authority_tier": label.get("label_authority_tier"),
        "review_status": label.get("review_status"),
        "training_eligible_now": bool(label.get("training_eligible") is True and label.get("review_status") == "approved"),
        "mutates_runtime_total": False,
    }
