#!/usr/bin/env python3
"""Export Factory2 blocked/positive crop datasets from proof receipts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-blocked-crop-dataset-v1"
DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.narrow_frozen_v2.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_blocked_crop_dataset.json")
DEFAULT_DATASET_DIR = Path("data/datasets/factory2_blocked_crops")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _label_placeholder(dataset_bucket: str) -> dict[str, str]:
    crop_label = "carried_panel" if dataset_bucket == "accepted_positive_boundary" else "unclear"
    return {
        "crop_label": crop_label,
        "mask_status": "missing",
        "notes": "",
    }


def _safe_name(path: str) -> str:
    return Path(path).parent.name or "unknown-diagnostic"


def _receipt_context(receipt_path: str | None) -> dict[str, Any]:
    if not receipt_path:
        return {}
    path = Path(receipt_path)
    if not path.exists():
        return {}
    return load_json(path)


def _separation_context(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    sidecar = Path(path)
    if not sidecar.exists():
        return {}
    return load_json(sidecar)


def _frame_context(
    *,
    index: int,
    selected_frames: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    frame: dict[str, Any] = {}
    if index < len(observations) and isinstance(observations[index], dict):
        frame.update(observations[index])
    if index < len(selected_frames) and isinstance(selected_frames[index], dict):
        frame.update(selected_frames[index])
    return frame


def _copy_crop(
    *,
    crop_path: Path,
    dataset_dir: Path,
    dataset_bucket: str,
    diagnostic_id: str,
    track_id: int,
    crop_index: int,
) -> Path:
    destination_dir = dataset_dir / dataset_bucket
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{diagnostic_id}-track-{track_id:06d}-crop-{crop_index:02d}{crop_path.suffix or '.jpg'}"
    shutil.copy2(crop_path, destination)
    return destination


def _rows_for_bucket(bucket: str, decision_index: dict[str, Any]) -> list[dict[str, Any]]:
    if bucket == "blocked_worker_overlap":
        rows = []
        for key in ["suppressed", "uncertain"]:
            for row in as_list(decision_index.get(key)):
                if isinstance(row, dict) and str(row.get("failure_link") or "") == "worker_body_overlap":
                    rows.append(row)
        return rows
    accepted_rows = []
    for row in as_list(decision_index.get("accepted")):
        if not isinstance(row, dict):
            continue
        if row.get("counts_toward_accepted_total") is False:
            continue
        accepted_rows.append(row)
    return accepted_rows


def export_blocked_crops(
    *,
    proof_report_path: Path,
    output_report_path: Path,
    dataset_dir: Path,
    force: bool,
) -> dict[str, Any]:
    if output_report_path.exists() and not force:
        raise FileExistsError(output_report_path)
    if dataset_dir.exists():
        if not force:
            raise FileExistsError(dataset_dir)
        shutil.rmtree(dataset_dir)

    proof_report = load_json(proof_report_path)
    decision_index = proof_report.get("decision_receipt_index") or {}
    items: list[dict[str, Any]] = []

    for dataset_bucket in ["blocked_worker_overlap", "accepted_positive_boundary"]:
        for row in _rows_for_bucket(dataset_bucket, decision_index):
            diagnostic_path = str(row.get("diagnostic_path") or "")
            diagnostic_id = Path(diagnostic_path).parent.name or _safe_name(diagnostic_path)
            track_id = int(row.get("track_id") or 0)
            receipt_payload = _receipt_context(str(row.get("receipt_json_path") or ""))
            separation_payload = _separation_context(str(row.get("person_panel_separation_path") or ""))
            selected_frames = [
                item
                for item in as_list(separation_payload.get("selected_frames"))
                if isinstance(item, dict)
            ]
            observations = [
                item
                for item in as_list((receipt_payload.get("evidence") or {}).get("observations"))
                if isinstance(item, dict)
            ]
            crop_paths = [Path(path) for path in as_list(row.get("raw_crop_paths")) if Path(path).exists()]

            for crop_index, crop_path in enumerate(crop_paths, start=1):
                frame = _frame_context(index=crop_index - 1, selected_frames=selected_frames, observations=observations)
                exported_crop = _copy_crop(
                    crop_path=crop_path,
                    dataset_dir=dataset_dir,
                    dataset_bucket=dataset_bucket,
                    diagnostic_id=diagnostic_id,
                    track_id=track_id,
                    crop_index=crop_index,
                )
                evidence = row.get("evidence_summary") or {}
                item = {
                    "dataset_bucket": dataset_bucket,
                    "diagnostic_id": diagnostic_id,
                    "diagnostic_path": diagnostic_path,
                    "window": row.get("window") or {},
                    "track_id": track_id,
                    "crop_index": crop_index,
                    "timestamp_seconds": frame.get("timestamp"),
                    "zone": frame.get("zone"),
                    "gate_decision": row.get("decision"),
                    "gate_reason": row.get("reason"),
                    "failure_link": row.get("failure_link"),
                    "worker_overlap_detail": row.get("worker_overlap_detail"),
                    "person_overlap_ratio": evidence.get("person_overlap_ratio"),
                    "outside_person_ratio": evidence.get("outside_person_ratio"),
                    "source_frames": evidence.get("source_frames"),
                    "output_frames": evidence.get("output_frames"),
                    "person_panel_recommendation": row.get("person_panel_recommendation"),
                    "person_panel_summary": row.get("person_panel_summary"),
                    "person_panel_separation_decision": frame.get("separation_decision"),
                    "receipt_json_path": row.get("receipt_json_path"),
                    "receipt_card_path": row.get("receipt_card_path"),
                    "receipt_timestamps": row.get("receipt_timestamps") or {},
                    "source_crop_path": str(crop_path),
                    "exported_crop_path": str(exported_crop),
                    "frame_path": frame.get("frame_path"),
                    "visual_receipt_path": frame.get("visual_receipt_path"),
                    "label_placeholder": _label_placeholder(dataset_bucket),
                }
                items.append(item)

    blocked_items = [item for item in items if item["dataset_bucket"] == "blocked_worker_overlap"]
    positive_items = [item for item in items if item["dataset_bucket"] == "accepted_positive_boundary"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "proof_report_path": str(proof_report_path),
        "dataset_dir": str(dataset_dir),
        "blocked_track_count": len(
            {
                (item["diagnostic_path"], item["track_id"])
                for item in blocked_items
            }
        ),
        "blocked_crop_count": len(blocked_items),
        "positive_track_count": len(
            {
                (item["diagnostic_path"], item["track_id"])
                for item in positive_items
            }
        ),
        "positive_crop_count": len(positive_items),
        "item_count": len(items),
        "items": items,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Factory2 blocked/positive crop datasets from proof receipts.")
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = export_blocked_crops(
        proof_report_path=args.proof_report,
        output_report_path=args.output_report,
        dataset_dir=args.dataset_dir,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
