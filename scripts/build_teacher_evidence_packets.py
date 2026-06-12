from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_evidence_packets import build_teacher_evidence_packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build teacher verification evidence packets from event proposals")
    parser.add_argument("--event-proposals", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sequence-fps", type=float, default=2.0)
    parser.add_argument("--max-packets", type=int)
    parser.add_argument("--max-width", type=int, default=960)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_teacher_evidence_packets(
            event_proposals_path=args.event_proposals,
            output_dir=args.output_dir,
            sequence_fps=args.sequence_fps,
            max_packets=args.max_packets,
            max_width=args.max_width,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output_dir": args.output_dir.as_posix(),
                "packet_count": payload["packet_count"],
                "manifest": (args.output_dir / "teacher_evidence_manifest.json").as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
