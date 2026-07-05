#!/usr/bin/env python3
"""Export static-resident reference crops from proof receipts rejected as static stack edges."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory2-static-resident-reference-crops-v1"
DEFAULT_PROOF_REPORT = Path("data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json")
DEFAULT_OUTPUT_REPORT = Path("data/reports/factory2_static_resident_reference_crops.v1.json")
DEFAULT_DATASET_DIR = Path("data/datasets/factory2_static_resident_reference_crops_v1")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def export_static_resident_reference_crops(
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
    suppressed = [row for row in as_list((proof_report.get("decision_receipt_index") or {}).get("suppressed")) if isinstance(row, dict)]

    export_dir = dataset_dir / "static_resident_reference"
    export_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for index, row in enumerate(suppressed, start=1):
        if str(row.get("reason") or "") != "static_stack_edge":
            continue
        raw_crop_paths = [Path(str(path)) for path in as_list(row.get("raw_crop_paths")) if str(path)]
        if not raw_crop_paths:
            continue
        source_crop = raw_crop_paths[0]
        if not source_crop.exists():
            continue
        diagnostic_stem = Path(str(row.get("diagnostic_path") or "diag")).parent.name or "diag"
        track_id = int(row.get("track_id") or 0)
        export_path = export_dir / f"{diagnostic_stem}-track-{track_id:06d}-static-reference{source_crop.suffix or '.jpg'}"
        shutil.copy2(source_crop, export_path)
        items.append(
            {
                "item_id": f"static-resident-ref-{index:06d}",
                "diagnostic_id": diagnostic_stem,
                "track_id": track_id,
                "event_id": "static-resident-reference",
                "track_role": "static_resident_reference",
                "track_class": "output_only",
                "source_receipt_json_path": row.get("receipt_json_path"),
                "receipt_timestamps": row.get("receipt_timestamps"),
                "exported_crop_path": str(export_path),
                "label_placeholder": {
                    "crop_label": "carried_panel",
                    "relation_label": "static_resident",
                    "notes": "proof static stack edge reference",
                },
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "proof_report_path": str(proof_report_path),
        "dataset_dir": str(dataset_dir),
        "candidate_count": len(items),
        "items": items,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Factory2 static-resident reference crops.")
    parser.add_argument("--proof-report", type=Path, default=DEFAULT_PROOF_REPORT)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = export_static_resident_reference_crops(
        proof_report_path=args.proof_report,
        output_report_path=args.output_report,
        dataset_dir=args.dataset_dir,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
