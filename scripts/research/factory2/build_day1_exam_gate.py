from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.holdout_split import author_holdout_case_manifest

PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
LEDGER_SCHEMA = "day1-human-exam-ledger-v1"


def parse_times(raw: str) -> list[float]:
    """Accept '3:05, 7:22, 12:41' or plain seconds '185, 442'; returns seconds from clip start."""
    times: list[float] = []
    for token in raw.replace("\n", ",").split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            parts = token.split(":")
            if len(parts) == 2:
                minutes, seconds = parts
                times.append(int(minutes) * 60 + float(seconds))
            elif len(parts) == 3:
                hours, minutes, seconds = parts
                times.append(int(hours) * 3600 + int(minutes) * 60 + float(seconds))
            else:
                raise ValueError(f"unparseable time token: {token!r}")
        else:
            times.append(float(token))
    return sorted(times)


def build_ledger(times: list[float], *, source_note: str) -> dict:
    return {
        "schema_version": LEDGER_SCHEMA,
        "counting_rule": "Human-reviewed placements scrubbed from the day-1 exam clip; times are seconds from clip start.",
        "source": source_note,
        "expected_human_total": len(times),
        "events": [
            {"truth_event_id": f"day1-exam-{index + 1:04d}", "event_ts": round(ts, 3), "count_total": index + 1}
            for index, ts in enumerate(times)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the day-1 exam: human placement times + exam clip + trained model -> blind replay gate"
    )
    parser.add_argument("--times", required=True, help="comma-separated placement times from clip start, e.g. '3:05, 7:22, 12:41'")
    parser.add_argument("--exam-clip", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True, help="the freshly trained station model (best.pt)")
    parser.add_argument("--station-id", default="factory-live-day1")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--playback-speed", type=float, default=8.0)
    parser.add_argument("--backend-port", type=int, default=8093)
    parser.add_argument("--frontend-port", type=int, default=5175)
    parser.add_argument("--dry-run", action="store_true", help="build ledger + manifest but skip the gate run")
    args = parser.parse_args(argv)

    times = parse_times(args.times)
    if not times:
        print("error: no placement times parsed", file=sys.stderr)
        return 1
    args.work_dir.mkdir(parents=True, exist_ok=True)
    ledger = build_ledger(times, source_note=f"typed by human reviewer for {args.exam_clip.name}")
    ledger_path = args.work_dir / "day1_exam_truth_ledger.json"
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path = args.work_dir / "day1_exam_case_manifest.json"
    author_holdout_case_manifest(
        station_id=args.station_id,
        holdout_clip_path=args.exam_clip,
        derived_ledger=ledger,
        derived_ledger_path=ledger_path,
        model_path=args.model,
        playback_speed=args.playback_speed,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        output_path=manifest_path,
        force=True,
    )
    print(json.dumps({"ledger": str(ledger_path), "manifest": str(manifest_path), "expected_total": len(times)}), flush=True)
    if args.dry_run:
        return 0

    gate_report = args.work_dir / "day1_blind_replay_gate.json"
    completed = subprocess.run(
        [
            PYTHON, "scripts/research/factory2/run_blind_replay_gate.py",
            "--manifest", str(manifest_path),
            "--output", str(gate_report),
            "--execute",
            "--backend-port", str(args.backend_port),
            "--frontend-port", str(args.frontend_port),
            "--force",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(f"gate run failed: {completed.stderr.strip()[-400:]}", file=sys.stderr)
        return 1
    report = json.loads(gate_report.read_text(encoding="utf-8"))
    print(json.dumps({
        "passed": report.get("passed"),
        "matched": report.get("matched_count"),
        "expected": report.get("expected_total"),
        "missing": report.get("missing_truth_count"),
        "unexpected": report.get("unexpected_observed_count"),
        "gate_report": str(gate_report),
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
