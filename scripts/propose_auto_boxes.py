from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.box_autolabeler import propose_auto_boxes, write_auto_box_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Propose bronze bounding-box labels for silver event candidates")
    parser.add_argument("--silver-dataset", type=Path, required=True)
    parser.add_argument("--packet-manifest", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", default="diff_box", choices=["diff_box", "yolo_world"])
    parser.add_argument("--class-name", default="active_panel")
    parser.add_argument("--class-prompt", default=None, help="open-vocabulary prompt for the yolo_world backend")
    parser.add_argument("--frames-per-event", type=int, default=3)
    parser.add_argument("--replicate-span-sec", type=float, default=3.0)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--yolo-world-model", type=Path, default=None)
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = propose_auto_boxes(
            silver_dataset_path=args.silver_dataset,
            packet_manifest_path=args.packet_manifest,
            work_dir=args.work_dir,
            backend=args.backend,
            class_name=args.class_name,
            class_prompt=args.class_prompt,
            frames_per_event=args.frames_per_event,
            replicate_span_sec=args.replicate_span_sec,
            val_fraction=args.val_fraction,
            yolo_world_model_path=args.yolo_world_model,
            allow_model_download=args.allow_model_download,
        )
        write_auto_box_manifest(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "backend": payload["backend"],
                "events_in": payload["summary"]["events_in"],
                "events_with_box": payload["summary"]["events_with_box"],
                "label_count": payload["summary"]["label_count"],
                "skipped_count": len(payload["summary"]["skipped"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
