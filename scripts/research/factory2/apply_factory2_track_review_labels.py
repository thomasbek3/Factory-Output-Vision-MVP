#!/usr/bin/env python3
"""Apply track-level review decisions back into Factory2 crop review CSV rows."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory2-track-review-application-v1"
REVIEW_PACKAGE_SCHEMA = "factory-crop-review-package-v1"
ALLOWED_LABELS = {"carried_panel", "worker_only", "static_stack", "unclear"}
DEFAULT_REVIEW_PACKAGE_REPORT = Path("data/reports/factory2_crop_review_package.narrow_frozen_v2.json")
DEFAULT_ORACLE_LABELS_JSON = Path("data/reports/factory2_track_labels.oracle.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_input_csv(
    review_package_report: dict[str, Any],
    review_package_report_path: Path,
    input_csv_path: Path | None,
) -> Path:
    if input_csv_path is not None:
        return input_csv_path
    csv_path = Path(str(review_package_report.get("review_labels_csv_path") or ""))
    if csv_path.is_absolute():
        return csv_path
    if csv_path.exists():
        return csv_path.resolve()
    return (review_package_report_path.parent / csv_path).resolve()


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        fieldnames = ["item_id", "crop_label", "mask_status", "notes"]
    else:
        fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _note_text(payload: dict[str, Any]) -> str:
    confidence = str(payload.get("confidence") or "").strip()
    reason = str(payload.get("short_reason") or "").strip()
    parts = ["oracle"]
    if confidence:
        parts.append(confidence)
    if reason:
        parts.append(reason)
    return ":".join(parts)


def apply_track_review_labels(
    *,
    review_package_report_path: Path,
    oracle_labels_json_path: Path,
    output_csv_path: Path,
    input_csv_path: Path | None,
    force: bool,
) -> dict[str, Any]:
    if output_csv_path.exists() and not force:
        raise FileExistsError(output_csv_path)

    review_package = load_json(review_package_report_path)
    if review_package.get("schema_version") != REVIEW_PACKAGE_SCHEMA:
        raise ValueError(f"Expected {REVIEW_PACKAGE_SCHEMA} review package")
    resolved_input_csv = _resolve_input_csv(review_package, review_package_report_path, input_csv_path)
    rows = _load_csv_rows(resolved_input_csv)
    package_items = {
        str(item.get("item_id") or ""): item
        for item in review_package.get("items", [])
        if isinstance(item, dict)
    }
    track_labels = load_json(oracle_labels_json_path)

    updated_row_count = 0
    updated_tracks: set[str] = set()
    for row in rows:
        item_id = str(row.get("item_id") or "")
        package_item = package_items.get(item_id)
        if not package_item:
            continue
        track_key = f"{package_item.get('diagnostic_id')}|{int(package_item.get('track_id') or 0)}"
        if track_key not in track_labels:
            continue
        payload = track_labels[track_key]
        crop_label = str(payload.get("crop_label") or "").strip()
        if crop_label not in ALLOWED_LABELS:
            raise ValueError(f"Unsupported crop_label {crop_label!r} for track {track_key}")
        row["crop_label"] = crop_label
        existing_notes = str(row.get("notes") or "").strip()
        note = _note_text(payload)
        row["notes"] = note if not existing_notes else f"{existing_notes} | {note}"
        updated_row_count += 1
        updated_tracks.add(track_key)

    _write_csv_rows(output_csv_path, rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "review_package_report_path": str(review_package_report_path),
        "input_csv_path": str(resolved_input_csv),
        "oracle_labels_json_path": str(oracle_labels_json_path),
        "output_csv_path": str(output_csv_path),
        "updated_row_count": updated_row_count,
        "updated_track_count": len(updated_tracks),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply track-level Factory2 crop review labels to review CSV rows.")
    parser.add_argument("--review-package-report", type=Path, default=DEFAULT_REVIEW_PACKAGE_REPORT)
    parser.add_argument("--oracle-labels-json", type=Path, default=DEFAULT_ORACLE_LABELS_JSON)
    parser.add_argument("--input-csv", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = apply_track_review_labels(
        review_package_report_path=args.review_package_report,
        oracle_labels_json_path=args.oracle_labels_json,
        output_csv_path=args.output_csv,
        input_csv_path=args.input_csv,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
