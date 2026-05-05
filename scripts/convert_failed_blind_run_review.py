#!/usr/bin/env python3
"""Convert a failed blind-run review worksheet into reviewed learning anchors."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_human_truth_ledger_from_csv import build_ledger


TRUE_DECISIONS = {
    "true_placement",
    "completed_placement",
    "countable",
    "accepted",
    "accept",
    "yes",
    "y",
    "true",
}
NEGATIVE_DECISIONS = {
    "hard_negative_static": "static_stack",
    "hard_negative_static_or_duplicate": "static_stack",
    "static_stack": "static_stack",
    "duplicate": "unclear",
    "worker_motion_only": "worker_only",
    "worker_only": "worker_only",
    "background": "unclear",
    "not_true_placement": "unclear",
    "negative": "unclear",
    "reject": "unclear",
    "rejected": "unclear",
    "no": "unclear",
    "n": "unclear",
    "false": "unclear",
}
UNCLEAR_DECISIONS = {"unclear", "needs_review", "needs_human_review"}
REQUIRED_WORKSHEET_COLUMNS = {
    "row_type",
    "candidate_id",
    "review_decision",
    "reviewed_event_ts",
}


class ReviewConversionError(ValueError):
    """Raised when a review worksheet cannot be promoted into anchors."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_event_ts(raw_value: str, *, row_number: int) -> float:
    value = raw_value.strip()
    if not value:
        raise ReviewConversionError(f"row {row_number}: reviewed_event_ts is required for true placements")
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ReviewConversionError(f"row {row_number}: reviewed_event_ts must be seconds or MM:SS.s")
        parsed = float(parts[0]) * 60.0 + float(parts[1])
    else:
        parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ReviewConversionError(f"row {row_number}: reviewed_event_ts must be a non-negative finite number")
    return round(parsed, 3)


def _expected_rows_from_packet(packet: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for slot in packet.get("truth_review_slots") or []:
        slot_id = str(slot.get("slot_id") or "")
        if slot_id:
            rows[slot_id] = "true_placement_slot"
    for candidate in packet.get("false_positive_candidates") or []:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id:
            rows[candidate_id] = "runtime_false_positive_candidate"
    for candidate in packet.get("motion_window_candidates") or []:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id:
            rows[candidate_id] = "possible_true_or_missed_event_window"
    return rows


def _read_worksheet_rows(worksheet_path: Path, *, packet: dict[str, Any]) -> list[dict[str, Any]]:
    expected_rows = _expected_rows_from_packet(packet)
    with worksheet_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = REQUIRED_WORKSHEET_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ReviewConversionError(
                f"{worksheet_path} missing columns: {', '.join(sorted(missing_columns))}"
            )
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            candidate_id = (row.get("candidate_id") or "").strip()
            row_type = (row.get("row_type") or "").strip()
            if not candidate_id:
                raise ReviewConversionError(f"row {row_number}: candidate_id is required")
            if candidate_id in seen:
                raise ReviewConversionError(f"row {row_number}: duplicate candidate_id {candidate_id}")
            expected_type = expected_rows.get(candidate_id)
            if expected_type is None:
                raise ReviewConversionError(f"row {row_number}: unknown candidate_id {candidate_id}")
            if row_type != expected_type:
                raise ReviewConversionError(
                    f"row {row_number}: row_type {row_type!r} does not match packet type {expected_type!r}"
                )
            row["_row_number"] = row_number
            rows.append(row)
            seen.add(candidate_id)

    missing_ids = sorted(set(expected_rows) - seen)
    if missing_ids:
        preview = ", ".join(missing_ids[:5])
        suffix = "" if len(missing_ids) <= 5 else f", ... ({len(missing_ids)} total)"
        raise ReviewConversionError(f"worksheet missing packet candidate rows: {preview}{suffix}")
    return rows


def _candidate_asset(packet: dict[str, Any], candidate_id: str, field: str) -> str | None:
    for collection_name in ("truth_review_slots", "false_positive_candidates", "motion_window_candidates"):
        for candidate in packet.get(collection_name) or []:
            if candidate.get("candidate_id") == candidate_id or candidate.get("slot_id") == candidate_id:
                value = candidate.get(field)
                return str(value) if value else None
    return None


def _classify_row(row: dict[str, Any]) -> dict[str, Any]:
    row_number = int(row["_row_number"])
    raw_decision = (row.get("review_decision") or "").strip()
    decision = raw_decision.lower()
    if not decision:
        return {
            "decision": "",
            "approved_status": None,
            "approved_event_ts_sec": None,
            "review_status": "pending",
            "label_authority_tier": "bronze",
            "validation_truth_eligible": False,
            "training_eligible": False,
            "is_true_placement": False,
            "is_hard_negative": False,
            "is_pending": True,
            "is_unclear": False,
        }
    if decision in TRUE_DECISIONS:
        return {
            "decision": decision,
            "approved_status": "completed",
            "approved_event_ts_sec": _parse_event_ts(row.get("reviewed_event_ts") or "", row_number=row_number),
            "review_status": "approved",
            "label_authority_tier": "gold",
            "validation_truth_eligible": True,
            "training_eligible": True,
            "is_true_placement": True,
            "is_hard_negative": False,
            "is_pending": False,
            "is_unclear": False,
        }
    if decision in NEGATIVE_DECISIONS:
        return {
            "decision": decision,
            "approved_status": NEGATIVE_DECISIONS[decision],
            "approved_event_ts_sec": None,
            "review_status": "approved",
            "label_authority_tier": "gold",
            "validation_truth_eligible": False,
            "training_eligible": True,
            "is_true_placement": False,
            "is_hard_negative": True,
            "is_pending": False,
            "is_unclear": False,
        }
    if decision in UNCLEAR_DECISIONS:
        return {
            "decision": decision,
            "approved_status": "unclear",
            "approved_event_ts_sec": None,
            "review_status": "unclear",
            "label_authority_tier": "bronze",
            "validation_truth_eligible": False,
            "training_eligible": False,
            "is_true_placement": False,
            "is_hard_negative": False,
            "is_pending": False,
            "is_unclear": True,
        }
    raise ReviewConversionError(f"row {row_number}: unsupported review_decision {raw_decision!r}")


def _build_label(
    *,
    row: dict[str, Any],
    classification: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    candidate_id = row["candidate_id"]
    notes = (row.get("notes") or "").strip()
    suggested = (row.get("suggested_review_decision") or "").strip()
    note_parts = []
    if suggested:
        note_parts.append(f"suggested_review_decision={suggested}")
    if notes:
        note_parts.append(notes)
    return {
        "label_id": f"{candidate_id}-review-label",
        "window_id": candidate_id,
        "candidate_type": row["row_type"],
        "source_id": (row.get("source_id") or "").strip() or None,
        "review_decision": classification["decision"],
        "review_status": classification["review_status"],
        "approved_status": classification["approved_status"],
        "approved_event_ts_sec": classification["approved_event_ts_sec"],
        "label_authority_tier": classification["label_authority_tier"],
        "validation_truth_eligible": classification["validation_truth_eligible"],
        "training_eligible": classification["training_eligible"],
        "sheet_path": (row.get("sheet_path") or "").strip() or _candidate_asset(packet, candidate_id, "sheet_path"),
        "clip_path": (row.get("clip_path") or "").strip() or _candidate_asset(packet, candidate_id, "clip_path"),
        "notes": "; ".join(note_parts),
    }


def _write_truth_csv(events: list[dict[str, Any]], path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["truth_event_id", "count_total", "event_ts", "notes"])
        writer.writeheader()
        writer.writerows(events)


def _split_for_training_index(index: int) -> str:
    if index % 11 == 0:
        return "test"
    if index % 5 == 0:
        return "val"
    return "train"


def _build_dataset_manifest(
    *,
    case_id: str,
    packet_path: Path,
    review_labels_path: Path,
    labels: list[dict[str, Any]],
    status: str,
    created_at: float,
) -> dict[str, Any]:
    splits: dict[str, list[dict[str, str]]] = {"train": [], "val": [], "test": [], "review": []}
    items: list[dict[str, Any]] = []
    training_index = 0
    for label in labels:
        if status == "reviewed_complete" and label["training_eligible"]:
            training_index += 1
            split = _split_for_training_index(training_index)
        else:
            split = "review"
        split_ref = {"item_id": label["label_id"], "window_id": label["window_id"]}
        splits.setdefault(split, []).append(split_ref)
        if label["review_status"] == "pending":
            label_kind = "pending_review"
        elif label["approved_status"] == "completed":
            label_kind = "true_placement"
        else:
            label_kind = "hard_negative_or_background"
        items.append(
            {
                "item_id": label["label_id"],
                "case_id": case_id,
                "window_id": label["window_id"],
                "event_id": label["window_id"] if label["approved_status"] == "completed" else None,
                "split": split,
                "evidence_path": packet_path.as_posix(),
                "label_path": review_labels_path.as_posix(),
                "label_authority_tier": label["label_authority_tier"],
                "review_status": label["review_status"],
                "teacher_output_status": label["approved_status"],
                "duplicate_risk": "unknown",
                "miss_risk": "high" if label["approved_status"] == "completed" else "unknown",
                "validation_truth_eligible": bool(label["validation_truth_eligible"]),
                "training_eligible": bool(label["training_eligible"]) and split != "review",
                "label_kind": label_kind,
                "approved_event_ts_sec": label["approved_event_ts_sec"],
                "sheet_path": label.get("sheet_path"),
                "clip_path": label.get("clip_path"),
            }
        )

    true_count = sum(1 for label in labels if label["approved_status"] == "completed")
    hard_negative_count = sum(1 for label in labels if label["training_eligible"] and label["approved_status"] != "completed")
    pending_count = sum(1 for label in labels if label["review_status"] == "pending")
    unclear_count = sum(1 for label in labels if label["review_status"] == "unclear")
    positive_box_labels_ready = False
    return {
        "schema_version": "factory-vision-active-learning-dataset-v1",
        "dataset_id": f"{case_id}-failed-blind-run-review-v1",
        "created_at": created_at,
        "case_ids": [case_id],
        "privacy_mode": "offline_local",
        "label_tier_policy": {
            "validation_truth_requires_gold": True,
            "bronze_training_allowed": False,
            "silver_validation_allowed": False,
        },
        "source_label_paths": [review_labels_path.as_posix()],
        "splits": {key: value for key, value in splits.items() if value},
        "items": items,
        "summary": {
            "true_placement_count": true_count,
            "hard_negative_count": hard_negative_count,
            "pending_count": pending_count,
            "unclear_count": unclear_count,
            "training_item_count": sum(1 for item in items if item["training_eligible"]),
            "review_item_count": sum(1 for item in items if item["split"] == "review"),
        },
        "detector_training": {
            "target_detector": "real_factory_specific_yolo",
            "positive_box_labels_ready": positive_box_labels_ready,
            "yolo_dataset_export_ready": status == "reviewed_complete" and positive_box_labels_ready,
            "blocked_reason": (
                "positive bounding boxes are not present in the failed-run review worksheet; "
                "use this manifest as reviewed event/window anchors before YOLO image-label export"
            ),
        },
    }


def _build_review_labels(
    *,
    case_id: str,
    packet_path: Path,
    reviewer_id: str,
    labels: list[dict[str, Any]],
    created_at: float,
) -> dict[str, Any]:
    reviewed_at = None if reviewer_id == "pending" else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_at))
    return {
        "schema_version": "factory-vision-review-labels-v1",
        "case_id": case_id,
        "created_at": created_at,
        "source_evidence_path": packet_path.as_posix(),
        "teacher_labels_path": None,
        "privacy_mode": "offline_local",
        "reviewer": {
            "type": "human",
            "id": reviewer_id,
            "reviewed_at": reviewed_at,
        },
        "labels": labels,
    }


def _manifest_video(manifest: dict[str, Any], packet: dict[str, Any]) -> tuple[str, str | None]:
    video = manifest.get("video") or {}
    video_path = video.get("path") or packet.get("source_video_path")
    video_sha = video.get("sha256") or packet.get("source_video_sha256")
    if not video_path:
        raise ReviewConversionError("manifest/packet does not provide a source video path")
    return str(video_path), str(video_sha) if video_sha else None


def convert_review(
    *,
    worksheet_path: Path,
    packet_path: Path,
    manifest_path: Path,
    status_path: Path,
    truth_csv_path: Path,
    truth_ledger_path: Path,
    review_labels_path: Path,
    dataset_manifest_path: Path,
    allow_pending: bool,
    force: bool,
    reviewer_id: str = "pending",
) -> dict[str, Any]:
    packet = read_json(packet_path)
    manifest = read_json(manifest_path)
    case_id = str(packet.get("case_id") or manifest.get("case_id") or "")
    if not case_id:
        raise ReviewConversionError("case_id is required")
    expected_total = int(packet.get("expected_true_total") or (manifest.get("truth") or {}).get("expected_total") or 0)
    if expected_total <= 0:
        raise ReviewConversionError("expected_true_total must be positive")

    rows = _read_worksheet_rows(worksheet_path, packet=packet)
    labels: list[dict[str, Any]] = []
    true_rows: list[dict[str, Any]] = []
    pending_count = 0
    unclear_count = 0
    for row in rows:
        classification = _classify_row(row)
        label = _build_label(row=row, classification=classification, packet=packet)
        labels.append(label)
        if classification["is_true_placement"]:
            true_rows.append({"row": row, "classification": classification, "label": label})
        if classification["is_pending"]:
            pending_count += 1
        if classification["is_unclear"]:
            unclear_count += 1

    if pending_count or unclear_count:
        if not allow_pending:
            raise ReviewConversionError(
                f"worksheet still has {pending_count} pending row(s) and {unclear_count} unclear row(s)"
            )
        status = "pending_human_review"
    else:
        status = "reviewed_complete"
        if len(true_rows) != expected_total:
            raise ReviewConversionError(
                f"expected {expected_total} true placement row(s), found {len(true_rows)}"
            )

    created_at = round(time.time(), 3)
    review_labels = _build_review_labels(
        case_id=case_id,
        packet_path=packet_path,
        reviewer_id=reviewer_id if status == "reviewed_complete" else "pending",
        labels=labels,
        created_at=created_at,
    )
    dataset_manifest = _build_dataset_manifest(
        case_id=case_id,
        packet_path=packet_path,
        review_labels_path=review_labels_path,
        labels=labels,
        status=status,
        created_at=created_at,
    )

    truth_events: list[dict[str, Any]] = []
    if status == "reviewed_complete":
        true_rows.sort(key=lambda item: (item["classification"]["approved_event_ts_sec"], int(item["row"]["_row_number"])))
        for index, item in enumerate(true_rows, start=1):
            label = item["label"]
            truth_events.append(
                {
                    "truth_event_id": f"{case_id}-truth-{index:04d}",
                    "count_total": index,
                    "event_ts": label["approved_event_ts_sec"],
                    "notes": f"source_candidate={label['window_id']}; review_decision={label['review_decision']}",
                }
            )
        _write_truth_csv(truth_events, truth_csv_path, force=force)
        video_path, video_sha = _manifest_video(manifest, packet)
        count_rule = str((manifest.get("truth") or {}).get("count_rule") or "")
        build_ledger(
            csv_path=truth_csv_path,
            output_path=truth_ledger_path,
            video_path=Path(video_path),
            expected_total=expected_total,
            count_rule=count_rule,
            video_sha256=video_sha,
            force=force,
        )

    write_json(review_labels_path, review_labels, force=force)
    write_json(dataset_manifest_path, dataset_manifest, force=force)

    hard_negative_count = sum(1 for label in labels if label["training_eligible"] and label["approved_status"] != "completed")
    summary = {
        "schema_version": "factory-vision-failed-blind-review-conversion-v1",
        "case_id": case_id,
        "created_at": created_at,
        "status": status,
        "worksheet_path": worksheet_path.as_posix(),
        "packet_path": packet_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "expected_true_total": expected_total,
        "accepted_true_placement_count": len(true_rows),
        "hard_negative_label_count": hard_negative_count,
        "pending_row_count": pending_count,
        "unclear_row_count": unclear_count,
        "validation_truth_eligible": status == "reviewed_complete",
        "training_eligible": status == "reviewed_complete",
        "truth_csv_path": truth_csv_path.as_posix() if status == "reviewed_complete" else None,
        "truth_ledger_path": truth_ledger_path.as_posix() if status == "reviewed_complete" else None,
        "review_labels_path": review_labels_path.as_posix(),
        "dataset_manifest_path": dataset_manifest_path.as_posix(),
        "detector_training": dataset_manifest["detector_training"],
        "authority_boundary": {
            "runtime_or_teacher_labels_are_truth": False,
            "requires_human_reviewed_event_timestamps": True,
            "requires_positive_box_labels_before_yolo_export": True,
        },
    }
    write_json(status_path, summary, force=force)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert failed blind-run review worksheet decisions into anchors")
    parser.add_argument("--worksheet", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--status-output", type=Path, required=True)
    parser.add_argument("--truth-csv", type=Path, required=True)
    parser.add_argument("--truth-ledger", type=Path, required=True)
    parser.add_argument("--review-labels", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--reviewer-id", default="pending")
    parser.add_argument("--allow-pending", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = convert_review(
            worksheet_path=args.worksheet,
            packet_path=args.packet,
            manifest_path=args.manifest,
            status_path=args.status_output,
            truth_csv_path=args.truth_csv,
            truth_ledger_path=args.truth_ledger,
            review_labels_path=args.review_labels,
            dataset_manifest_path=args.dataset_manifest,
            reviewer_id=args.reviewer_id,
            allow_pending=args.allow_pending,
            force=args.force,
        )
    except (FileExistsError, ReviewConversionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
