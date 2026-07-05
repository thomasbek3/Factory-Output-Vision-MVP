from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.station_calibration import build_station_calibration, write_station_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a station calibration file")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--output-polygon", required=True, help="normalized polygon JSON string")
    parser.add_argument("--source-polygon", default=None, help="optional normalized polygon JSON string")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        source_polygons = [json.loads(args.source_polygon)] if args.source_polygon is not None else []
        payload = build_station_calibration(
            station_id=args.station_id,
            source_polygons=source_polygons,
            output_polygons=[json.loads(args.output_polygon)],
        )
        write_station_calibration(args.out, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": args.out.as_posix(), "station_id": args.station_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
