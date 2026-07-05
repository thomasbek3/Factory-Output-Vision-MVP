from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any


DEFAULT_GROWTH_WINDOWS = [["12:26", "13:05"], ["13:47", "16:27"]]
DEFAULT_STALL_WINDOWS = [["13:05", "13:47"]]


@dataclass(frozen=True)
class WallWindow:
    start: datetime
    end: datetime

    def contains(self, value: datetime) -> bool:
        return self.start <= value < self.end


def build_zone_mining_validation(
    *,
    proposals_path: Path,
    growth_windows: list[list[str]],
    stall_windows: list[list[str]],
    date_text: str,
    top_n: int,
) -> dict[str, Any]:
    payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    events = [row for row in payload.get("proposals") or [] if row.get("candidate_type") == "event_candidate"]
    dated_growth_windows = _parse_windows(growth_windows, date_text=date_text)
    dated_stall_windows = _parse_windows(stall_windows, date_text=date_text)
    rows = []
    for event in events:
        wall_time = proposal_wall_time(event)
        if wall_time is None:
            continue
        rows.append(
            {
                "candidate_id": event.get("candidate_id"),
                "wall_time": wall_time,
                "wall_time_text": wall_time.strftime("%H:%M:%S"),
                "zone_score": float(event.get("peak_motion_score_output_zone") or 0.0),
            }
        )
    ranked = sorted(rows, key=lambda row: row["zone_score"], reverse=True)[:top_n]
    heavy_growth_window = dated_growth_windows[-1] if dated_growth_windows else None
    growth_count = sum(1 for row in ranked if _in_any(row["wall_time"], dated_growth_windows))
    heavy_growth_count = (
        sum(1 for row in ranked if heavy_growth_window.contains(row["wall_time"]))
        if heavy_growth_window is not None
        else 0
    )
    stall_count = sum(1 for row in ranked if _in_any(row["wall_time"], dated_stall_windows))
    outside_count = len(ranked) - growth_count - stall_count
    bucket_counts = _bucket_counts(rows)
    verdict = "PASS" if ranked and growth_count / float(len(ranked)) >= 0.60 and heavy_growth_count >= 10 and stall_count == 0 else "FAIL"
    return {
        "schema_version": "factory-vision-zone-mining-validation-v1",
        "proposals_path": str(proposals_path),
        "date": date_text,
        "top_n": int(top_n),
        "verdict": verdict,
        "summary": {
            "event_candidate_count": len(events),
            "ranked_count": len(ranked),
            "growth_window_count": growth_count,
            "heavy_growth_window_count": heavy_growth_count,
            "stall_window_count": stall_count,
            "outside_window_count": outside_count,
        },
        "bucket_counts_15min": bucket_counts,
        "top_20": [
            {
                "candidate_id": row["candidate_id"],
                "wall_time": row["wall_time_text"],
                "zone_score": round(row["zone_score"], 6),
            }
            for row in ranked[:20]
        ],
    }


def proposal_wall_time(proposal: dict[str, Any]) -> datetime | None:
    segment_path = Path(str(proposal.get("segment_path") or ""))
    try:
        start = datetime.strptime(segment_path.name.split("_", 1)[0], "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    return start + timedelta(seconds=float(proposal.get("center_offset_sec") or 0.0))


def print_human_table(report: dict[str, Any]) -> None:
    print("15-min buckets")
    for bucket, count in report["bucket_counts_15min"].items():
        print(f"{bucket}: {count}")
    print("top 20")
    for row in report["top_20"]:
        print(f"{row['wall_time']}  {row['zone_score']:.6f}  {row['candidate_id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate output-zone mining against known Day-1 growth windows")
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--growth-windows", default=json.dumps(DEFAULT_GROWTH_WINDOWS))
    parser.add_argument("--stall-windows", default=json.dumps(DEFAULT_STALL_WINDOWS))
    parser.add_argument("--date", default="2026-06-11")
    parser.add_argument("--top-n", type=int, default=70)
    args = parser.parse_args(argv)

    try:
        report = build_zone_mining_validation(
            proposals_path=args.proposals,
            growth_windows=json.loads(args.growth_windows),
            stall_windows=json.loads(args.stall_windows),
            date_text=args.date,
            top_n=args.top_n,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    print_human_table(report)
    return 0 if report["verdict"] == "PASS" else 1


def _parse_windows(raw_windows: list[list[str]], *, date_text: str) -> list[WallWindow]:
    date_value = datetime.strptime(date_text, "%Y-%m-%d").date()
    windows = []
    for raw_start, raw_end in raw_windows:
        start = datetime.combine(date_value, _parse_hhmm(raw_start))
        end = datetime.combine(date_value, _parse_hhmm(raw_end))
        windows.append(WallWindow(start=start, end=end))
    return windows


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _in_any(value: datetime, windows: list[WallWindow]) -> bool:
    return any(window.contains(value) for window in windows)


def _bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        wall_time = row["wall_time"]
        minute = (wall_time.minute // 15) * 15
        bucket = wall_time.replace(minute=minute, second=0, microsecond=0).strftime("%H:%M")
        counts[bucket] = counts.get(bucket, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
