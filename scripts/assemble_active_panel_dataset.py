#!/usr/bin/env python3
"""Assemble a YOLO dataset from AI-reviewed positives and hard negatives.

This is the bridge between the label QA gate / diagnostic hard-negative loop and
actual active_panel retraining. Positives must come from the reviewed label gate;
negative examples come from scripts/export_hard_negatives.py and are written with
empty YOLO label files.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "active-panel-yolo-dataset-v1"
CLASS_NAMES = ["active_panel"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


def resolve_path(value: str | None, *, base: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (base / path).resolve()


def yolo_line_from_xyxy(box: list[float], *, width: int, height: int, class_index: int = 0) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("Image width/height must be positive")
    if len(box) != 4:
        raise ValueError("Expected xyxy box with four coordinates")
    x1, y1, x2, y2 = [float(v) for v in box]
    x1 = max(0.0, min(float(width), x1))
    x2 = max(0.0, min(float(width), x2))
    y1 = max(0.0, min(float(height), y1))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Degenerate box after clipping: {box}")
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"{class_index} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def copy_asset(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_data_yaml(out_dir: Path) -> Path:
    path = out_dir / "data.yaml"
    path.write_text(
        "path: .\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: active_panel\n",
        encoding="utf-8",
    )
    return path


def load_reviewed_positives(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = load_json(path)
    if payload.get("schema_version") != "label-quality-reviewed-v1":
        raise ValueError("Expected reviewed label manifest schema_version label-quality-reviewed-v1")
    return list(payload.get("trainable_labels") or [])


def load_hard_negative_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = load_json(path)
    if payload.get("schema_version") != "factory-hard-negative-export-v1":
        raise ValueError("Expected hard negative export schema_version factory-hard-negative-export-v1")
    return list(payload.get("items") or [])


def add_positive_label(*, label: dict[str, Any], reviewed_manifest_path: Path, out_dir: Path, index: int) -> dict[str, Any]:
    metadata = label.get("metadata") or {}
    src = resolve_path(metadata.get("frame_path") or label.get("image_path"), base=reviewed_manifest_path.parent)
    if src is None:
        raise ValueError(f"Positive label {label.get('label_id')} is missing metadata.frame_path")
    suffix = src.suffix if src.suffix.lower() in IMAGE_EXTENSIONS else ".jpg"
    split = str(label.get("split") or metadata.get("split") or "train")
    stem = f"pos-{index:06d}-{safe_stem(str(label.get('label_id') or label.get('frame_id') or index))}"
    image_dst = out_dir / "images" / split / f"{stem}{suffix}"
    label_dst = out_dir / "labels" / split / f"{stem}.txt"
    copy_asset(src, image_dst)
    line = yolo_line_from_xyxy(
        list(label.get("box") or []),
        width=int(label.get("image_width") or 0),
        height=int(label.get("image_height") or 0),
    )
    label_dst.parent.mkdir(parents=True, exist_ok=True)
    label_dst.write_text(line + "\n", encoding="utf-8")
    return {
        "kind": "positive",
        "label_id": label.get("label_id"),
        "source_image_path": str(src),
        "image_path": str(image_dst),
        "label_path": str(label_dst),
        "split": split,
        "class_name": "active_panel",
    }


def add_negative_row(*, row: dict[str, Any], hard_negative_export_path: Path, out_dir: Path, index: int) -> dict[str, Any]:
    src = resolve_path(row.get("exported_image_path") or row.get("source_asset_path"), base=hard_negative_export_path.parent)
    if src is None:
        raise ValueError(f"Hard negative row {row.get('negative_id')} is missing image asset path")
    suffix = src.suffix if src.suffix.lower() in IMAGE_EXTENSIONS else ".jpg"
    split = str(row.get("split") or "train")
    stem = f"neg-{index:06d}-{safe_stem(str(row.get('negative_id') or index))}"
    image_dst = out_dir / "images" / split / f"{stem}{suffix}"
    label_dst = out_dir / "labels" / split / f"{stem}.txt"
    copy_asset(src, image_dst)
    label_dst.parent.mkdir(parents=True, exist_ok=True)
    label_dst.write_text("", encoding="utf-8")
    return {
        "kind": "hard_negative",
        "negative_id": row.get("negative_id"),
        "reason": row.get("reason"),
        "review_only": bool(row.get("review_only")),
        "source_image_path": str(src),
        "image_path": str(image_dst),
        "label_path": str(label_dst),
        "split": split,
    }


def assemble_dataset(
    *,
    out_dir: Path,
    reviewed_label_manifest: Path | None,
    hard_negative_export: Path | None,
    force: bool = False,
    allow_negative_only: bool = False,
) -> Path:
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise FileExistsError(f"Refusing to overwrite non-empty output directory: {out_dir}")
    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    positives = load_reviewed_positives(reviewed_label_manifest)
    negatives = load_hard_negative_rows(hard_negative_export)
    if not positives and not allow_negative_only:
        raise ValueError("No reviewed positive labels found; pass --allow-negative-only for a negative-only eval dataset")

    rows: list[dict[str, Any]] = []
    if reviewed_label_manifest is not None:
        for index, label in enumerate(positives, start=1):
            rows.append(add_positive_label(label=label, reviewed_manifest_path=reviewed_label_manifest, out_dir=out_dir, index=index))
    if hard_negative_export is not None:
        for index, row in enumerate(negatives, start=1):
            rows.append(add_negative_row(row=row, hard_negative_export_path=hard_negative_export, out_dir=out_dir, index=index))

    data_yaml = write_data_yaml(out_dir)
    manifest_path = out_dir / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "class_names": CLASS_NAMES,
                "data_yaml_path": str(data_yaml),
                "reviewed_label_manifest": str(reviewed_label_manifest) if reviewed_label_manifest else None,
                "hard_negative_export": str(hard_negative_export) if hard_negative_export else None,
                "summary": {
                    "positive_count": len(positives),
                    "hard_negative_count": len(negatives),
                    "total_images": len(rows),
                    "empty_negative_labels": len(negatives),
                },
                "items": rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble YOLO active_panel dataset with hard negatives")
    parser.add_argument("--reviewed-label-manifest", type=Path, default=None)
    parser.add_argument("--hard-negative-export", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-negative-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = assemble_dataset(
        out_dir=args.out_dir,
        reviewed_label_manifest=args.reviewed_label_manifest,
        hard_negative_export=args.hard_negative_export,
        force=args.force,
        allow_negative_only=args.allow_negative_only,
    )
    print(json.dumps({"dataset_manifest": str(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
