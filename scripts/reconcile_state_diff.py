from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.state_diff_reconciler import build_state_diff_reconciliation, write_state_diff_reconciliation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile teacher labels against before/after state-diff evidence")
    parser.add_argument("--packet-manifest", type=Path, required=True)
    parser.add_argument("--teacher-labels", type=Path)
    parser.add_argument("--diff-threshold", type=float, default=0.02)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_state_diff_reconciliation(
            packet_manifest_path=args.packet_manifest,
            teacher_labels_path=args.teacher_labels,
            diff_threshold=args.diff_threshold,
        )
        write_state_diff_reconciliation(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "packet_count": payload["summary"]["packet_count"],
                "state_change_count": payload["summary"]["state_change_count"],
                "matched_assert_count": payload["summary"]["matched_assert_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
