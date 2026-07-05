#!/usr/bin/env python3
"""Export worker-only reference crop candidates from nearby non-track frames."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image


SCHEMA_VERSION = "factory2-worker-reference-crops-v1"
REVIEW_PACKAGE_SCHEMA = "factory-crop-review-package-v1"
DEFAULT_REVIEW_PACKAGE_REPORT = Path("data/reports/factory2_crop_review_package.narrow_frozen_v2.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_worker_reference_crops.narrow_frozen_v2.json")
DEFAULT_DATASET_DIR = Path("data/datasets/factory2_worker_reference_crops_narrow_frozen_v2")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_review_labels_csv(
    review_package_report: dict[str, Any],
    review_package_report_path: Path,
    review_labels_csv_path: Path | None,
) -> Path:
    if review_labels_csv_path is not None:
        return review_labels_csv_path
    csv_path = Path(str(review_package_report.get("review_labels_csv_path") or ""))
    if csv_path.is_absolute():
        return csv_path
    if csv_path.exists():
        return csv_path.resolve()
    return (review_package_report_path.parent / csv_path).resolve()


def _load_review_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {str(row.get("item_id") or "").strip(): dict(row) for row in csv.DictReader(handle)}


def _sidecar_path(receipt_json_path: str) -> Path:
    receipt_path = Path(receipt_json_path)
    return receipt_path.with_name(receipt_path.stem + "-person-panel-separation.json")


def _parse_frame_index(path: str) -> int:
    stem = Path(path).stem
    try:
        return int(stem.split("_")[-1])
    except ValueError as exc:
        raise ValueError(f"Could not parse frame index from {path}") from exc


def _crop_xywh(image: Image.Image, box_xywh: list[float]) -> Image.Image:
    cx, cy, w, h = [float(v) for v in box_xywh]
    left = max(0, int(round(cx - w / 2.0)))
    top = max(0, int(round(cy - h / 2.0)))
    right = min(image.width, int(round(cx + w / 2.0)))
    bottom = min(image.height, int(round(cy + h / 2.0)))
    return image.crop((left, top, right, bottom))


def _candidate_frame_paths(frame_path: Path) -> dict[int, Path]:
    frames_dir = frame_path.parent
    return {
        _parse_frame_index(str(candidate)): candidate
        for candidate in sorted(frames_dir.glob("frame_*.jpg"))
    }


def _best_reference_frame(
    *,
    selected_frame_path: Path,
    selected_frame_paths: list[Path],
    observed_frame_paths: set[Path],
) -> Path | None:
    selected_indices = sorted(_parse_frame_index(str(path)) for path in selected_frame_paths)
    first_index = selected_indices[0]
    last_index = selected_indices[-1]
    candidates = _candidate_frame_paths(selected_frame_path)
    for step in range(2, 9):
        candidate = candidates.get(first_index - step)
        if candidate is not None and candidate not in observed_frame_paths:
            return candidate
    for step in range(2, 9):
        candidate = candidates.get(last_index + step)
        if candidate is not None and candidate not in observed_frame_paths:
            return candidate
    for step in range(1, 9):
        for direction in (-1, 1):
            candidate = candidates.get(first_index + (direction * step))
            if candidate is None:
                continue
            if first_index <= _parse_frame_index(str(candidate)) <= last_index:
                continue
            if candidate in observed_frame_paths:
                continue
            return candidate
    return None


def export_worker_reference_crops(
    *,
    review_package_report_path: Path,
    review_labels_csv_path: Path | None,
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

    review_package = load_json(review_package_report_path)
    if review_package.get("schema_version") != REVIEW_PACKAGE_SCHEMA:
        raise ValueError(f"Expected {REVIEW_PACKAGE_SCHEMA} review package")
    resolved_csv = _resolve_review_labels_csv(review_package, review_package_report_path, review_labels_csv_path)
    review_rows = _load_review_rows(resolved_csv)

    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for item in review_package.get("items", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "")
        if str((review_rows.get(item_id) or {}).get("crop_label") or "").strip() != "carried_panel":
            continue
        key = (str(item.get("diagnostic_id") or "diag"), int(item.get("track_id") or 0))
        grouped.setdefault(key, item)

    items: list[dict[str, Any]] = []
    export_dir = dataset_dir / "reference_worker_only_candidate"
    export_dir.mkdir(parents=True, exist_ok=True)

    for (diagnostic_id, track_id), item in sorted(grouped.items()):
        receipt_json_path = Path(str(item.get("receipt_json_path") or ""))
        if not receipt_json_path.exists():
            continue
        sidecar_path = _sidecar_path(str(receipt_json_path))
        if not sidecar_path.exists():
            continue
        receipt = load_json(receipt_json_path)
        sidecar = load_json(sidecar_path)
        selected_frames = [frame for frame in sidecar.get("selected_frames", []) if isinstance(frame, dict)]
        if not selected_frames:
            continue
        selected = next((frame for frame in selected_frames if frame.get("person_box_xywh")), None)
        if selected is None:
            continue
        selected_frame_path = Path(str(selected.get("frame_path") or ""))
        selected_frame_paths = [Path(str(frame.get("frame_path") or "")) for frame in selected_frames if frame.get("frame_path")]
        observed_frame_paths = {
            Path(str(obs.get("frame_path")))
            for obs in (receipt.get("evidence") or {}).get("observations", [])
            if isinstance(obs, dict) and obs.get("frame_path")
        }
        reference_frame = _best_reference_frame(
            selected_frame_path=selected_frame_path,
            selected_frame_paths=selected_frame_paths,
            observed_frame_paths=observed_frame_paths,
        )
        if reference_frame is None:
            continue
        image = Image.open(reference_frame).convert("RGB")
        crop = _crop_xywh(image, list(selected.get("person_box_xywh") or []))
        export_path = export_dir / f"{diagnostic_id}-track-{track_id:06d}-worker-reference.jpg"
        crop.save(export_path)
        items.append(
            {
                "dataset_bucket": "reference_worker_only_candidate",
                "diagnostic_id": diagnostic_id,
                "track_id": track_id,
                "source_receipt_json_path": str(receipt_json_path),
                "source_sidecar_path": str(sidecar_path),
                "selected_frame_path": str(selected_frame_path),
                "sampled_frame_path": str(reference_frame),
                "person_box_xywh": selected.get("person_box_xywh"),
                "label_placeholder": {
                    "crop_label": "worker_only",
                    "mask_status": "missing",
                    "notes": "nearby_nontrack_person_box",
                },
                "exported_crop_path": str(export_path),
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "review_package_report_path": str(review_package_report_path),
        "review_labels_csv_path": str(resolved_csv),
        "dataset_dir": str(dataset_dir),
        "candidate_count": len(items),
        "items": items,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Factory2 worker-only reference crop candidates.")
    parser.add_argument("--review-package-report", type=Path, default=DEFAULT_REVIEW_PACKAGE_REPORT)
    parser.add_argument("--review-labels-csv", type=Path, default=None)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = export_worker_reference_crops(
        review_package_report_path=args.review_package_report,
        review_labels_csv_path=args.review_labels_csv,
        output_report_path=args.output_report,
        dataset_dir=args.dataset_dir,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
