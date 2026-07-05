from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.auto_station_calibration import derive_station_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive runtime calibration zones from auto-box landing regions and train-clip motion"
    )
    parser.add_argument("--auto-boxes", type=Path, required=True)
    parser.add_argument("--train-clip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = derive_station_calibration(
            auto_boxes_path=args.auto_boxes,
            train_clip_path=args.train_clip,
            output_path=args.output,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "output_polygon": payload["output_polygons"][0],
                "source_polygon": payload["source_polygons"][0],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
