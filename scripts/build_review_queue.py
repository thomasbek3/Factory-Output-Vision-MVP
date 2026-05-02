#!/usr/bin/env python3
"""Build a reviewer-ready queue from event evidence and advisory teacher labels."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-review-queue-v1"
RISK_SCORE = {"high": 45, "medium": 25, "unknown": 10, "low": 0}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _label_by_window(teacher_labels: dict[str, Any]) -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    for label in teacher_labels.get("labels") or []:
        labels[str(label["window_id"])] = label
    return labels


def _best_frame_asset(window: dict[str, Any]) -> dict[str, Any] | None:
    assets = [
        asset
        for asset in ((window.get("review_window") or {}).get("frame_assets") or [])
        if asset.get("status") == "written" and asset.get("frame_path")
    ]
    if not assets:
        return None
    center_sec = (window.get("time_window") or {}).get("center_sec")
    if center_sec is None:
        return assets[0]
    return min(assets, key=lambda asset: abs(float(asset.get("timestamp_sec") or 0.0) - float(center_sec)))


def _candidate_use(status: str, confidence: str) -> str:
    if status in {"worker_only", "static_stack"} and confidence in {"high", "medium"}:
        return "hard_negative_review"
    if status in {"countable", "completed", "in_transit"} and confidence in {"high", "medium"}:
        return "positive_review"
    return "needs_human_review"


def _priority(label: dict[str, Any]) -> tuple[int, list[str], str]:
    status = str(label.get("teacher_output_status") or "unclear")
    confidence = str(label.get("confidence_tier") or "unknown")
    duplicate_risk = str(label.get("duplicate_risk") or "unknown")
    miss_risk = str(label.get("miss_risk") or "unknown")
    reasons: list[str] = []
    score = 0

    if status == "unclear":
        score += 100
        reasons.append("teacher_unclear")
    if confidence in {"low", "unknown"}:
        score += 30
        reasons.append(f"confidence_{confidence}")
    if duplicate_risk != "low":
        score += RISK_SCORE.get(duplicate_risk, 10)
        reasons.append(f"duplicate_risk_{duplicate_risk}")
    if miss_risk != "low":
        score += RISK_SCORE.get(miss_risk, 10)
        reasons.append(f"miss_risk_{miss_risk}")
    if status in {"worker_only", "static_stack"} and confidence in {"high", "medium"}:
        score += 60
        reasons.append("hard_negative_candidate")
    if status in {"countable", "completed", "in_transit"} and confidence == "high":
        score += 5
        reasons.append("positive_candidate")

    if score >= 100:
        bucket = "review_first"
    elif "hard_negative_candidate" in reasons:
        bucket = "hard_negative_review"
    else:
        bucket = "routine_review"
    return score, reasons, bucket


def _queue_entry(*, rank: int, window: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    score, reasons, bucket = _priority(label)
    frame_assets = (window.get("review_window") or {}).get("frame_assets") or []
    primary_frame_asset = _best_frame_asset(window)
    status = str(label.get("teacher_output_status") or "unclear")
    confidence = str(label.get("confidence_tier") or "unknown")
    return {
        "queue_id": f"review-{rank:04d}",
        "rank": rank,
        "window_id": window["window_id"],
        "window_type": window.get("window_type"),
        "priority_score": score,
        "priority_bucket": bucket,
        "review_reasons": reasons,
        "candidate_use": _candidate_use(status, confidence),
        "teacher_label_id": label.get("label_id"),
        "teacher_output_status": status,
        "confidence_tier": confidence,
        "duplicate_risk": label.get("duplicate_risk", "unknown"),
        "miss_risk": label.get("miss_risk", "unknown"),
        "rationale": label.get("rationale", ""),
        "suggested_event_ts_sec": label.get("suggested_event_ts_sec"),
        "time_window": window.get("time_window", {}),
        "frame_window": window.get("frame_window", {}),
        "review_question": (window.get("review_window") or {}).get("review_question"),
        "primary_frame_asset": primary_frame_asset,
        "frame_assets": frame_assets,
        "count_event_evidence": window.get("count_event_evidence"),
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


def build_review_queue(*, evidence_path: Path, teacher_labels_path: Path) -> dict[str, Any]:
    evidence = read_json(evidence_path)
    teacher_labels = read_json(teacher_labels_path)
    labels = _label_by_window(teacher_labels)
    entries = [
        _queue_entry(rank=0, window=window, label=labels.get(str(window["window_id"]), {}))
        for window in evidence.get("windows") or []
    ]
    entries.sort(
        key=lambda entry: (
            -int(entry["priority_score"]),
            float((entry.get("time_window") or {}).get("center_sec") or 0.0),
            str(entry["window_id"]),
        )
    )
    for index, entry in enumerate(entries, start=1):
        entry["rank"] = index
        entry["queue_id"] = f"review-{index:04d}"

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": evidence["case_id"],
        "created_at": round(time.time(), 3),
        "source_evidence_path": evidence_path.as_posix(),
        "teacher_labels_path": teacher_labels_path.as_posix(),
        "privacy_mode": evidence.get("privacy_mode", "offline_local"),
        "provider": teacher_labels.get("provider"),
        "refuses_validation_truth": True,
        "queue": entries,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review queue from event evidence and teacher labels")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_review_queue(evidence_path=args.evidence, teacher_labels_path=args.teacher_labels)
    write_json(args.output, payload, force=args.force)
    counts: dict[str, int] = {}
    for entry in payload["queue"]:
        bucket = str(entry["priority_bucket"])
        counts[bucket] = counts.get(bucket, 0) + 1
    print(json.dumps({"output": args.output.as_posix(), "queue_count": len(payload["queue"]), "buckets": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
