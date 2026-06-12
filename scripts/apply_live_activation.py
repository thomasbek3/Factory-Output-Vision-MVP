from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.live_activation import apply_live_activation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Factory Vision live activation config after blind replay gate")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    parser.add_argument("--station-calibration", type=Path, required=True)
    parser.add_argument("--camera-ip", required=True)
    parser.add_argument("--camera-username", required=True)
    parser.add_argument("--camera-password", required=True)
    parser.add_argument("--stream-profile", choices=["sub", "main"], default="sub")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--yolo-confidence", type=float)
    parser.add_argument("--event-count-rule", choices=["auto", "dead_track", "placed_and_stayed"], default="placed_and_stayed")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = apply_live_activation(
            station_id=args.station_id,
            gate_report_path=args.gate_report,
            station_calibration_path=args.station_calibration,
            camera_config={
                "camera_ip": args.camera_ip,
                "camera_username": args.camera_username,
                "camera_password": args.camera_password,
                "stream_profile": args.stream_profile,
            },
            model_path=args.model,
            yolo_confidence=args.yolo_confidence,
            event_count_rule=args.event_count_rule,
            output_path=args.output,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "status": payload["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
