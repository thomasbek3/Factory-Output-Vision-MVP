#!/usr/bin/env python3
"""Export diagnostic hard negatives into review/training-prep assets.

The diagnostic hard-negative manifest is forensic evidence. This exporter turns it
into a stable review manifest and, optionally, empty YOLO-label negative images.

Important: current diagnostic assets are receipt cards/overlays, not clean raw
training frames. The exported manifest marks every row as review_only unless a
future diagnostic adds raw frame/crop assets.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUTPUT_DIR = Path("data/labels/hard_negatives")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export diagnostic hard negatives for QA/retraining prep.")
    parser.add_argument("manifests", nargs="+", type=Path, help="One or more hard_negative_manifest.json files")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--split", default="train", choices=["train", "val", "test", "review"])
    parser.add_argument("--include-uncertain", action="store_true", help="Include uncertain_negative rows as well as hard_negative")
    parser.add_argument("--write-yolo-negatives", action="store_true", help="Copy review images and write empty YOLO .txt labels")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    export = export_hard_negatives(
        manifest_paths=args.manifests,
        out_dir=args.out_dir,
        split=args.split,
        include_uncertain=args.include_uncertain,
        write_yolo_negatives=args.write_yolo_negatives,
        force=args.force,
    )
    print(json.dumps({"export_manifest": str(export), "out_dir": str(args.out_dir)}, sort_keys=True))
    return 0


def export_hard_negatives(
    *,
    manifest_paths: list[Path],
    out_dir: Path,
    split: str = "train",
    include_uncertain: bool = False,
    write_yolo_negatives: bool = False,
    force: bool = False,
) -> Path:
    if not manifest_paths:
        raise ValueError("At least one manifest path is required")
    prepare_output_dir(out_dir, force=force)

    image_dir = out_dir / "images" / split
    label_dir = out_dir / "labels" / split
    if write_yolo_negatives:
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        manifest = load_hard_negative_manifest(manifest_path)
        for index, item in enumerate(manifest.get("items", [])):
            if not should_export_item(item, include_uncertain=include_uncertain):
                continue
            row = build_export_row(
                item,
                manifest_path=manifest_path,
                source_index=index,
                out_dir=out_dir,
                split=split,
                write_yolo_negative=write_yolo_negatives,
            )
            rows.append(row)

    payload = {
        "schema_version": "factory-hard-negative-export-v1",
        "source_manifests": [str(path) for path in manifest_paths],
        "count": len(rows),
        "include_uncertain": include_uncertain,
        "write_yolo_negatives": write_yolo_negatives,
        "review_only": True,
        "items": rows,
    }
    export_path = out_dir / "hard_negative_export.json"
    export_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return export_path


def prepare_output_dir(out_dir: Path, *, force: bool) -> None:
    if out_dir.exists():
        if not force and any(out_dir.iterdir()):
            raise FileExistsError(f"Refusing to overwrite non-empty output directory without --force: {out_dir}")
        if force:
            shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def load_hard_negative_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "factory-hard-negative-manifest-v1":
        raise ValueError(f"Unsupported hard-negative manifest schema in {path}")
    if not isinstance(payload.get("items"), list):
        raise ValueError(f"Hard-negative manifest must contain an items list: {path}")
    return payload


def should_export_item(item: dict[str, Any], *, include_uncertain: bool) -> bool:
    label = item.get("label")
    if label == "hard_negative":
        return True
    if include_uncertain and label == "uncertain_negative":
        return True
    return False


def build_export_row(
    item: dict[str, Any],
    *,
    manifest_path: Path,
    source_index: int,
    out_dir: Path,
    split: str,
    write_yolo_negative: bool,
) -> dict[str, Any]:
    assets = item.get("assets") or {}
    source_asset = resolve_asset_path(assets.get("track_sheet_path") or assets.get("receipt_path"), manifest_path=manifest_path)
    stem = make_export_stem(manifest_path=manifest_path, item=item, source_index=source_index)
    exported_image_path = None
    exported_label_path = None
    if write_yolo_negative and source_asset is not None:
        suffix = source_asset.suffix or ".jpg"
        exported_image = out_dir / "images" / split / f"{stem}{suffix}"
        exported_label = out_dir / "labels" / split / f"{stem}.txt"
        shutil.copy2(source_asset, exported_image)
        exported_label.write_text("", encoding="utf-8")
        exported_image_path = str(exported_image)
        exported_label_path = str(exported_label)

    return {
        "negative_id": stem,
        "label": item.get("label"),
        "reason": item.get("reason"),
        "track_id": item.get("track_id"),
        "source_manifest": str(manifest_path),
        "source_asset_path": str(source_asset) if source_asset is not None else None,
        "exported_image_path": exported_image_path,
        "exported_label_path": exported_label_path,
        "yolo_class_name": "active_panel",
        "yolo_label_contents": "",
        "review_only": True,
        "training_note": "Empty-label negative from diagnostic receipt/overlay; review before using for detector training.",
        "evidence": item.get("evidence"),
        "gate_decision": item.get("gate_decision"),
        "diagnosis": item.get("diagnosis"),
    }


def resolve_asset_path(value: Any, *, manifest_path: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend([REPO_ROOT / path, manifest_path.parent / path])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def make_export_stem(*, manifest_path: Path, item: dict[str, Any], source_index: int) -> str:
    parent = manifest_path.parent.name.replace("/", "-").replace(" ", "-")
    track_id = int(item.get("track_id", source_index + 1))
    label = str(item.get("label", "negative")).replace("_", "-")
    reason = str(item.get("reason", "unknown")).replace("_", "-")
    return f"{parent}-track-{track_id:06d}-{label}-{reason}"


if __name__ == "__main__":
    raise SystemExit(main())
