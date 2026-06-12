from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.teacher_grading import (
    grade_teacher_labels_against_truth,
    write_teacher_grade_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grade teacher verification labels against a reviewed human truth ledger (diagnostic only)"
    )
    parser.add_argument("--teacher-labels", type=Path, required=True)
    parser.add_argument("--truth-ledger", type=Path, required=True)
    parser.add_argument("--packet-manifest", type=Path, default=None, help="evidence manifest to resolve packet windows/segments")
    parser.add_argument("--segment-manifest", type=Path, default=None, help="recorder segment manifest to map segment-relative timestamps onto the source video timeline")
    parser.add_argument("--segment-offset-sec", type=float, default=0.0)
    parser.add_argument("--dedupe-window-sec", type=float, default=2.0)
    parser.add_argument("--tolerance-sec", type=float, action="append", default=None, help="repeatable; defaults to 2, 5, 10")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    tolerances = tuple(args.tolerance_sec) if args.tolerance_sec else (2.0, 5.0, 10.0)
    try:
        payload = grade_teacher_labels_against_truth(
            teacher_labels_path=args.teacher_labels,
            truth_ledger_path=args.truth_ledger,
            tolerances_sec=tolerances,
            packet_manifest_path=args.packet_manifest,
            segment_manifest_path=args.segment_manifest,
            segment_offset_sec=args.segment_offset_sec,
            dedupe_window_sec=args.dedupe_window_sec,
        )
        write_teacher_grade_report(args.output, payload, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    headline_key = "5" if "5" in payload["per_tolerance"] else sorted(payload["per_tolerance"])[0]
    headline = payload["per_tolerance"][headline_key]
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "provider": payload["provider"]["name"],
                "decision_histogram": payload["decision_histogram"],
                "truth_event_count": payload["truth_event_count"],
                "deduped_prediction_count": payload["deduped_prediction_count"],
                f"precision@{headline_key}s": headline["precision"],
                f"recall@{headline_key}s": headline["recall"],
                "true_positives": headline["true_positives"],
                "false_positives": headline["false_positives"],
                "false_negatives": headline["false_negatives"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
