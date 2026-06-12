from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_fusion import build_teacher_fusion_report, write_teacher_fusion_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fuse teacher verifications with state-diff reconciliation")
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--state-diff", type=Path, required=True)
    parser.add_argument("--silver-dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = build_teacher_fusion_report(
            teacher_labels_path=args.teacher_labels,
            state_diff_path=args.state_diff,
            output_dataset_path=args.silver_dataset,
        )
        write_teacher_fusion_report(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "silver_candidate_count": payload["summary"]["silver_candidate_count"],
                "needs_review_count": payload["summary"]["needs_review_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
