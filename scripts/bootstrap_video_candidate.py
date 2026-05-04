#!/usr/bin/env python3
"""Bootstrap the repeatable fast path for a new factory video candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_COUNT_RULE = (
    "Count one completed placement when the worker finishes putting the finished product "
    "in the output/resting area."
)
DEFAULT_REGISTRY = Path("validation/registry.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _duration(payload: dict[str, Any]) -> float:
    raw = (payload.get("format") or {}).get("duration")
    if raw not in (None, "N/A"):
        return round(float(raw), 6)
    for stream in payload.get("streams") or []:
        raw = stream.get("duration")
        if raw not in (None, "N/A"):
            return round(float(raw), 6)
    raise ValueError("ffprobe payload has no duration")


def _video_stream(payload: dict[str, Any]) -> dict[str, Any]:
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("ffprobe payload has no video stream")


def metadata_from_ffprobe(payload: dict[str, Any]) -> dict[str, Any]:
    stream = _video_stream(payload)
    return {
        "duration_sec": _duration(payload),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": str(stream.get("codec_name") or "unknown"),
        "fps": str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "unknown"),
        "frame_count": None if stream.get("nb_frames") in (None, "N/A") else int(stream["nb_frames"]),
    }


def _load_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        return {"schema_version": "factory-vision-validation-registry-v1", "cases": []}
    return json.loads(registry_path.read_text(encoding="utf-8"))


def _load_manifest_for_case(case_id: str, *, registry_path: Path) -> dict[str, Any]:
    registry = _load_registry(registry_path)
    for entry in registry.get("cases") or []:
        if entry.get("case_id") == case_id:
            return json.loads(Path(entry["manifest_path"]).read_text(encoding="utf-8"))
    raise KeyError(f"baseline case not found in {registry_path}: {case_id}")


def build_total_payload(
    *,
    video_path: Path,
    video_sha256: str,
    metadata: dict[str, Any],
    expected_total: int | None,
    human_counter: str | None,
    truth_rule_id: str,
    count_rule: str,
    today: date | None = None,
) -> dict[str, Any]:
    is_blind = expected_total is None
    return {
        "schema_version": "human-truth-total-v1",
        "video_path": video_path.as_posix(),
        "video_sha256": video_sha256,
        "duration_sec": metadata["duration_sec"],
        "human_counter": human_counter,
        "expected_human_total": expected_total,
        "truth_rule_id": truth_rule_id,
        "count_rule": count_rule,
        "verification_status": (
            "blind_estimate_pending_human_reveal" if is_blind else "provisional_total_only"
        ),
        "timestamp_truth_status": "not_requested_blind_phase" if is_blind else "not_reviewed_yet",
        "validation_truth_eligible": False,
        "validation_note": (
            "Blind candidate placeholder only. The hidden human total has not been requested "
            "or revealed; produce an AI/app estimate before comparison."
            if is_blind
            else (
                "This total is the starting human reference. It can drive diagnostics, but "
                "candidate verification still requires reviewed timestamp truth plus clean "
                "real-app app-vs-truth comparison."
            )
        ),
        "created_at": (today or date.today()).isoformat(),
    }


def build_candidate_manifest(
    *,
    case_id: str,
    display_name: str,
    video_path: Path,
    video_sha256: str,
    metadata: dict[str, Any],
    expected_total: int | None,
    truth_rule_id: str,
    count_rule: str,
    human_total_path: Path,
    truth_ledger_path: Path,
    baseline_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict((baseline_manifest or {}).get("runtime") or {})
    runtime.setdefault("demo_count_mode", "live_reader_snapshot")
    runtime.setdefault("counting_mode", "event_based")
    runtime.setdefault("playback_speed", 1.0)
    runtime.setdefault("processing_fps", 10.0)
    runtime.setdefault("reader_fps", 10.0)
    runtime.setdefault("runtime_calibration_path", None)
    runtime.setdefault("model_path", None)

    return {
        "schema_version": "factory-vision-video-manifest-v1",
        "case_id": case_id,
        "display_name": display_name,
        "status": "candidate",
        "promotion_status": "not_promoted",
        "verified_at": None,
        "video": {
            "path": video_path.as_posix(),
            "sha256": video_sha256,
            "duration_sec": metadata["duration_sec"],
            "width": metadata["width"],
            "height": metadata["height"],
            "codec": metadata["codec"],
        },
        "truth": {
            "rule_id": truth_rule_id,
            "expected_total": expected_total,
            "count_rule": count_rule,
            "truth_ledger_path": truth_ledger_path.as_posix(),
            "human_total_path": human_total_path.as_posix(),
            "human_total_status": (
                "hidden_not_requested_blind_phase" if expected_total is None else "provisional_total_only"
            ),
            "validation_truth_eligible": False,
            "notes": [
                (
                    "Blind bootstrap candidate manifest only; no human expected total has been requested "
                    "or revealed."
                    if expected_total is None
                    else "Bootstrap candidate manifest only."
                ),
                "Do not mark verified until visible 1.0x app run and clean app-vs-reviewed-truth exist.",
            ],
        },
        "runtime": runtime,
        "launch": {
            "backend_port": 8092,
            "frontend_port": 5174,
            "command": [],
            "dashboard_url": "http://127.0.0.1:5174/dashboard",
        },
        "proof_artifacts": {
            "observed_events": f"data/reports/{case_id}_app_observed_events.visible_dashboard_1x_v1.json",
            "comparison_report": f"data/reports/{case_id}_app_vs_truth.visible_dashboard_1x_v1.json",
            "validation_report": f"data/reports/{case_id}_validation_report.registry_v1.json",
            "pacing_report": f"data/reports/{case_id}_wall_source_pacing.visible_dashboard_1x_v1.json",
            "screenshots": [],
        },
        "proof_summary": {},
    }


def build_next_steps(
    *, case_id: str, video_path: Path, expected_total: int | None, baseline_case_id: str | None
) -> list[str]:
    baseline_note = baseline_case_id or "the nearest verified case"
    target_note = (
        f"Use the human total {expected_total} as the target, not as proof."
        if expected_total is not None
        else "Keep this phase blind: produce the AI/app estimated total before requesting the hidden human total."
    )
    return [
        f"1. Run detector transfer screen against {baseline_note}; stop if sampled recall is near zero.",
        (
            "   .venv/bin/python scripts/screen_detector_transfer.py "
            f"--video {video_path.as_posix()} --model <baseline-model.pt> "
            f"--output data/reports/{case_id}_detector_transfer_screen.v1.json --force"
        ),
        "2. If transfer fails, build a small video-specific diagnostic detector before a long dashboard run.",
        f"3. {target_note}",
        "4. Run accelerated real-app diagnostics and compare to the draft/reviewed ledger.",
        "5. Only run the visible 1.0x dashboard proof after diagnostics are plausible.",
        "6. If final total matches but event diff has swaps, make a focused dispute packet and reconcile it locally.",
        f"7. Register {case_id} only after app-vs-reviewed-truth is clean.",
        f"Video: {video_path.as_posix()}",
    ]


def write_truth_template(path: Path, *, case_id: str, expected_total: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["truth_event_id", "count_total", "event_ts", "notes"])
        writer.writeheader()
        for index in range(1, expected_total + 1):
            writer.writerow(
                {
                    "truth_event_id": f"{case_id}-truth-{index:04d}",
                    "count_total": index,
                    "event_ts": "",
                    "notes": "pending reviewed timestamp",
                }
            )


def write_blind_truth_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["truth_event_id", "count_total", "event_ts", "notes"])
        writer.writeheader()


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    video_path = args.video
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    probe_payload = ffprobe(video_path)
    metadata = metadata_from_ffprobe(probe_payload)
    video_sha256 = sha256_file(video_path)
    stem = args.artifact_stem or args.case_id
    reports_dir = Path("data/reports")
    expected_total = parse_expected_total(args.expected_total)
    if args.blind:
        if expected_total is not None:
            raise ValueError("--blind cannot be combined with a numeric --expected-total")
        expected_total = None
    truth_rule_id = (
        "blind_estimate_pending_human_reveal"
        if expected_total is None and args.truth_rule_id == "completed_placement_total_only_v1"
        else args.truth_rule_id
    )

    fingerprint_path = reports_dir / f"{stem}_video_fingerprint.v1.json"
    human_total_path = reports_dir / f"{stem}_human_truth_total.v1.json"
    truth_csv_path = (
        reports_dir / f"{stem}_human_truth_event_times.pending_reveal.csv"
        if expected_total is None
        else reports_dir / f"{stem}_human_truth_event_times.template.csv"
    )
    truth_ledger_path = reports_dir / f"{stem}_human_truth_ledger.reviewed_v1.json"
    manifest_path = args.manifest or Path("validation/test_cases") / f"{args.case_id}.candidate.json"

    baseline_manifest = None
    if args.baseline_case_id:
        baseline_manifest = _load_manifest_for_case(args.baseline_case_id, registry_path=args.registry)

    fingerprint_payload = {
        "schema_version": "factory-vision-video-fingerprint-v1",
        "video_path": video_path.as_posix(),
        "sha256": video_sha256,
        **metadata,
    }
    total_payload = build_total_payload(
        video_path=video_path,
        video_sha256=video_sha256,
        metadata=metadata,
        expected_total=expected_total,
        human_counter=None if expected_total is None else args.human_counter,
        truth_rule_id=truth_rule_id,
        count_rule=args.count_rule,
    )
    manifest_payload = build_candidate_manifest(
        case_id=args.case_id,
        display_name=args.display_name or f"{args.case_id} candidate",
        video_path=video_path,
        video_sha256=video_sha256,
        metadata=metadata,
        expected_total=expected_total,
        truth_rule_id=truth_rule_id,
        count_rule=args.count_rule,
        human_total_path=human_total_path,
        truth_ledger_path=truth_ledger_path,
        baseline_manifest=baseline_manifest,
    )
    next_steps = build_next_steps(
        case_id=args.case_id,
        video_path=video_path,
        expected_total=expected_total,
        baseline_case_id=args.baseline_case_id,
    )

    if not args.dry_run:
        write_json(fingerprint_path, fingerprint_payload, force=args.force)
        write_json(human_total_path, total_payload, force=args.force)
        write_json(manifest_path, manifest_payload, force=args.force)
        if truth_csv_path.exists() and not args.force:
            raise FileExistsError(truth_csv_path)
        if expected_total is None:
            write_blind_truth_placeholder(truth_csv_path)
        else:
            write_truth_template(truth_csv_path, case_id=args.case_id, expected_total=expected_total)
        if args.preview:
            subprocess.run(
                [
                    ".venv/bin/python",
                    "scripts/preview_video_frames.py",
                    video_path.as_posix(),
                    "--out-dir",
                    f"data/videos/preview_sheets/{args.case_id}",
                    "--force",
                ],
                check=True,
            )

    return {
        "mode": "dry-run" if args.dry_run else "write",
        "case_id": args.case_id,
        "video_sha256": video_sha256,
        "metadata": metadata,
        "artifacts": {
            "fingerprint": fingerprint_path.as_posix(),
            "human_total": human_total_path.as_posix(),
            "truth_template": truth_csv_path.as_posix(),
            "candidate_manifest": manifest_path.as_posix(),
        },
        "next_steps": next_steps,
    }


def parse_expected_total(raw: str | None) -> int | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"", "unknown", "blind", "none", "null"}:
        return None
    value = int(raw)
    if value <= 0:
        raise ValueError("--expected-total must be positive or unknown")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a fast-path Factory Vision video candidate")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--expected-total")
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--display-name")
    parser.add_argument("--artifact-stem")
    parser.add_argument("--human-counter", default="Thomas")
    parser.add_argument("--truth-rule-id", default="completed_placement_total_only_v1")
    parser.add_argument("--count-rule", default=DEFAULT_COUNT_RULE)
    parser.add_argument("--baseline-case-id", default="img2628_candidate")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    print(json.dumps(bootstrap(parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
