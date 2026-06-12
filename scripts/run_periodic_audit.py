from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.periodic_audit import build_periodic_audit_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a periodic audit dispute/retraining report")
    parser.add_argument("--observed-events", type=Path, required=True)
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_periodic_audit_report(
            observed_events_path=args.observed_events,
            teacher_labels_path=args.teacher_labels,
            output_path=args.output,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "dispute_count": len(payload["disputes"]),
                "retraining_trigger_count": len(payload["retraining_triggers"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
