#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.clip_models import arch_availability, train_arch_selection, write_synthetic_clip_manifest

VIDEO_ARCHES = {"video_x3d", "video_vmae"}


def synthetic_smoke_image_size(arch: str) -> int:
    return 64 if arch == "all" or arch in VIDEO_ARCHES else 32


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train Day-4 clip action-recognition student models.")
    parser.add_argument("--manifest", type=Path, help="Labeled clip manifest. Required unless --synthetic-smoke is set.")
    parser.add_argument("--arch", choices=["stack3_mobilenet", "video_x3d", "video_vmae", "twostream", "all"], required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--pretrained", action="store_true", help="Try ImageNet/pretrained backbones where available.")
    parser.add_argument("--synthetic-smoke", action="store_true", help="Create a tiny synthetic labeled manifest for smoke tests.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    manifest_path = args.manifest
    if args.synthetic_smoke:
        manifest_path = args.out_dir / "synthetic_manifest.json"
        write_synthetic_clip_manifest(manifest_path, image_size=synthetic_smoke_image_size(args.arch))
    if manifest_path is None:
        parser.error("--manifest is required unless --synthetic-smoke is set")

    results = train_arch_selection(
        manifest_path=manifest_path,
        arch=args.arch,
        out_dir=args.out_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
        pretrained=args.pretrained,
    )
    payload = {
        "results": results,
        "availability": {
            name: {"available": status.available, "reason": status.reason}
            for name, status in arch_availability().items()
        },
        "comparison_table": str(args.out_dir / "comparison_table.md"),
    }
    (args.out_dir / "comparison.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    failed = [row for row in results if row.get("status") not in {"trained", "skipped"}]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
