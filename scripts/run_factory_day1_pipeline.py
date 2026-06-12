from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
PROPOSAL_MODES = {"full_frame_motion", "output_zone_motion"}


def split_recorder_manifest(
    *,
    segment_manifest_path: Path,
    work_dir: Path,
    holdout_fraction: float,
) -> dict[str, Path]:
    """Split a recorder manifest into a train-portion manifest and a concatenated holdout exam clip.

    No truth ledger exists on day 1, so the split is purely by segment count: the first
    ~(1-fraction) of segments feed the training lane; the tail becomes the exam clip that a
    human scrubs afterward to produce the answer key."""
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    segments = sorted(manifest.get("segments") or [], key=lambda row: str(row.get("path")))
    if len(segments) < 4:
        raise ValueError(f"only {len(segments)} segments; need at least 4 to split")
    holdout_count = max(1, round(len(segments) * holdout_fraction))
    train_segments = segments[: len(segments) - holdout_count]
    holdout_segments = segments[len(segments) - holdout_count :]

    work_dir.mkdir(parents=True, exist_ok=True)
    train_manifest_path = work_dir / "train_segment_manifest.json"
    train_manifest = dict(manifest)
    train_manifest["segments"] = train_segments
    train_manifest["day1_split"] = {
        "total_segments": len(segments),
        "train_segments": len(train_segments),
        "holdout_segments": len(holdout_segments),
        "holdout_fraction": holdout_fraction,
    }
    train_manifest_path.write_text(json.dumps(train_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # MKV recorder chunks carry timestamps the concat muxer rejects when stream-copied
    # directly; remuxing each chunk to mp4 first (instant, no re-encode) normalizes them.
    remux_dir = work_dir / "holdout_remux"
    remux_dir.mkdir(parents=True, exist_ok=True)
    remuxed_paths: list[Path] = []
    for index, row in enumerate(holdout_segments):
        remuxed = remux_dir / f"seg{index:03d}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(row["path"]), "-c", "copy", "-video_track_timescale", "90000", str(remuxed)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        remuxed_paths.append(remuxed)
    concat_list = work_dir / "holdout_concat_list.txt"
    concat_list.write_text("".join(f"file '{path}'\n" for path in remuxed_paths), encoding="utf-8")
    exam_clip = work_dir / "exam_clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(exam_clip)],
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return {"train_manifest": train_manifest_path, "exam_clip": exam_clip, "holdout_count": len(holdout_segments)}


def cap_event_proposals(
    proposals_path: Path,
    *,
    max_events: int,
    proposal_mode: str = "full_frame_motion",
    teacher_negative_cap: int | None = None,
) -> dict[str, int]:
    """Evenly subsample event proposals across the whole recording so a long busy morning
    doesn't explode teacher cost; keeps all stable hard negatives."""
    payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    rows = payload.get("proposals") or []
    events = [row for row in rows if row.get("candidate_type") == "event_candidate"]
    negatives = [row for row in rows if row.get("candidate_type") != "event_candidate"]
    if proposal_mode == "output_zone_motion":
        kept = _ranked_zone_event_cap(events=events, max_events=max_events, min_center_gap_sec=20.0)
        sampling = "top_n_zone_score_time_dedup"
    else:
        kept = _even_stride(events, max_events)
        sampling = "even_stride_across_recording"
    kept_negatives, local_negatives = _cap_negatives(negatives=negatives, teacher_negative_cap=teacher_negative_cap)
    payload["proposals"] = kept + kept_negatives
    if local_negatives:
        payload["local_negative_proposals"] = local_negatives
    payload.setdefault("summary", {})["day1_event_cap"] = {
        "events_total": len(events),
        "events_kept": len(kept),
        "sampling": sampling,
    }
    payload["summary"]["teacher_negative_cap"] = {
        "negatives_total": len(negatives),
        "negatives_packetized": len(kept_negatives),
        "local_negative_not_teacher_judged": len(local_negatives),
    }
    proposals_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "events_total": len(events),
        "events_kept": len(kept),
        "negatives_total": len(negatives),
        "negatives_packetized": len(kept_negatives),
        "local_negative_not_teacher_judged": len(local_negatives),
    }


def append_local_negative_labels(*, teacher_labels_path: Path, proposals_path: Path) -> int:
    proposals_payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    local_negatives = proposals_payload.get("local_negative_proposals") or []
    if not local_negatives:
        return 0
    labels_payload = json.loads(teacher_labels_path.read_text(encoding="utf-8"))
    labels = list(labels_payload.get("labels") or [])
    for proposal in local_negatives:
        packet_id = str(proposal.get("candidate_id") or proposal.get("window_id"))
        labels.append(
            {
                "label_id": f"{packet_id}-local-negative-not-teacher-judged",
                "packet_id": packet_id,
                "window_id": proposal.get("window_id") or packet_id,
                "candidate_id": proposal.get("candidate_id"),
                "source_packet_manifest_path": None,
                "teacher_output_status": "local_negative_not_teacher_judged",
                "verification_decision": "refute_completed",
                "suggested_event_ts_sec": None,
                "confidence_tier": "medium",
                "duplicate_risk": "low",
                "miss_risk": "unknown",
                "rationale": "Local stable-negative proposal outside the teacher budget. No visual teacher inspected it.",
                "label_authority_tier": "bronze",
                "review_status": "pending",
                "validation_truth_eligible": False,
                "training_eligible": False,
            }
        )
    labels_payload["labels"] = labels
    labels_payload.setdefault("summary", {})["local_negative_not_teacher_judged"] = len(local_negatives)
    teacher_labels_path.write_text(json.dumps(labels_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(local_negatives)


def _ranked_zone_event_cap(*, events: list[dict[str, Any]], max_events: int, min_center_gap_sec: float) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    kept_times: list[datetime] = []
    ranked = sorted(events, key=lambda row: float(row.get("peak_motion_score_output_zone") or 0.0), reverse=True)
    for event in ranked:
        center = _proposal_center_wall_time(event)
        if center is not None and any(abs((center - kept_time).total_seconds()) <= min_center_gap_sec for kept_time in kept_times):
            continue
        kept.append(event)
        if center is not None:
            kept_times.append(center)
        if len(kept) >= max_events:
            break
    return kept


def _even_stride(events: list[dict[str, Any]], max_events: int) -> list[dict[str, Any]]:
    if max_events <= 0:
        return []
    if len(events) <= max_events:
        return events
    if max_events == 1:
        return [events[len(events) // 2]]
    stride_indices = sorted({round(i * (len(events) - 1) / (max_events - 1)) for i in range(max_events)})
    return [events[i] for i in stride_indices]


def _cap_negatives(
    *,
    negatives: list[dict[str, Any]],
    teacher_negative_cap: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if teacher_negative_cap is None or len(negatives) <= teacher_negative_cap:
        return negatives, []
    kept = _even_stride(negatives, teacher_negative_cap)
    kept_ids = {id(row) for row in kept}
    return kept, [row for row in negatives if id(row) not in kept_ids]


def _proposal_center_wall_time(proposal: dict[str, Any]) -> datetime | None:
    raw = proposal.get("source_start_wall_ts")
    if raw:
        text = str(raw).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text) + timedelta(seconds=float(proposal.get("center_offset_sec") or 0.0))
        except ValueError:
            return None
    try:
        start = datetime.strptime(Path(str(proposal["segment_path"])).name.split("_", 1)[0], "%Y%m%dT%H%M%S")
    except (KeyError, ValueError):
        return None
    return start.replace(tzinfo=timezone.utc) + timedelta(seconds=float(proposal.get("center_offset_sec") or 0.0))


def run_stage(name: str, command: list[str]) -> None:
    print(json.dumps({"stage": name, "status": "running"}), flush=True)
    completed = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        print(json.dumps({"stage": name, "status": "failed", "stderr": completed.stderr.strip()[-500:]}), flush=True)
        raise SystemExit(f"stage {name} failed")
    print(json.dumps({"stage": name, "status": "completed"}), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Day-1 factory pipeline: recorder manifest -> teacher -> boxes -> trained model (no truth needed). "
        "The exam clip is produced for the human answer key; gating happens later via build_holdout_case tools."
    )
    parser.add_argument("--segment-manifest", type=Path, required=True, help="recorder segment_manifest.json")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--station-id", default="factory-live-day1")
    parser.add_argument("--holdout-fraction", type=float, default=0.3)
    parser.add_argument("--teacher-provider", default="codex_cli")
    parser.add_argument("--allow-cloud", action="store_true")
    parser.add_argument("--teacher-batch-size", type=int, default=4)
    parser.add_argument("--station-calibration", type=Path, default=None)
    parser.add_argument("--proposal-mode", choices=sorted(PROPOSAL_MODES), default="full_frame_motion")
    parser.add_argument("--teacher-negative-cap", type=int, default=30)
    parser.add_argument("--base-model", type=Path, default=Path("yolov8n.pt"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--max-teacher-events", type=int, default=70, help="cap on event candidates sent to the teacher (evenly sampled across the morning)")
    parser.add_argument("--split-only", action="store_true", help="only produce train manifest + exam clip, then stop")
    args = parser.parse_args(argv)

    work = args.work_dir
    split = split_recorder_manifest(
        segment_manifest_path=args.segment_manifest,
        work_dir=work,
        holdout_fraction=args.holdout_fraction,
    )
    print(json.dumps({"stage": "split", "status": "completed", "exam_clip": str(split["exam_clip"]), "holdout_segments": split["holdout_count"]}), flush=True)
    if args.split_only:
        return 0

    train_manifest = split["train_manifest"]
    proposals = work / "event_proposals.json"
    packets_dir = work / "packets"
    packet_manifest = packets_dir / "teacher_evidence_manifest.json"
    teacher_labels = work / "teacher_verifications.json"
    state_diff = work / "state_diff.json"
    fusion = work / "teacher_fusion.json"
    silver = work / "silver_candidates.json"
    auto_boxes = work / "auto_boxes.json"
    reviewed = work / "reviewed_labels.json"
    hard_negatives_dir = work / "hard_negatives"
    dataset_dir = work / "dataset"
    training_report = work / "training_eval.json"
    trained_model = work / "train" / "model" / "weights" / "best.pt"

    teacher_cmd = [
        PYTHON, "scripts/generate_teacher_verifications.py",
        "--packet-manifest", str(packet_manifest),
        "--provider", args.teacher_provider,
        "--batch-size", str(args.teacher_batch_size),
        "--output", str(teacher_labels), "--force",
    ]
    if args.allow_cloud:
        teacher_cmd.insert(4, "--allow-cloud")

    proposal_cmd = [PYTHON, "scripts/propose_onboarding_events.py", "--segment-manifest", str(train_manifest), "--output", str(proposals), "--sample-fps", "2", "--motion-threshold", "0.01", "--proposal-mode", args.proposal_mode, "--min-cluster-gap-sec", "1.5", "--window-before-sec", "6", "--window-after-sec", "6", "--stable-negative-count", "3", "--force"]
    packets_cmd = [PYTHON, "scripts/build_teacher_evidence_packets.py", "--event-proposals", str(proposals), "--output-dir", str(packets_dir), "--sequence-fps", "2", "--max-width", "960", "--force"]
    if args.station_calibration is not None:
        proposal_cmd.extend(["--station-calibration", str(args.station_calibration)])
        packets_cmd.extend(["--station-calibration", str(args.station_calibration)])
    stages = [
        ("proposals", proposal_cmd),
        ("packets", packets_cmd),
        ("teacher", teacher_cmd),
        ("reconcile", [PYTHON, "scripts/reconcile_state_diff.py", "--packet-manifest", str(packet_manifest), "--teacher-labels", str(teacher_labels), "--output", str(state_diff), "--force"]),
        ("fuse", [PYTHON, "scripts/fuse_teacher_verifications.py", "--teacher-labels", str(teacher_labels), "--state-diff", str(state_diff), "--silver-dataset", str(silver), "--output", str(fusion), "--force"]),
        ("boxes", [PYTHON, "scripts/propose_auto_boxes.py", "--silver-dataset", str(silver), "--packet-manifest", str(packet_manifest), "--work-dir", str(work / "boxes"), "--output", str(auto_boxes), "--backend", "diff_box", "--frames-per-event", "6", "--force"]),
        ("review", [PYTHON, "scripts/review_labels_ai.py", str(auto_boxes), "--output", str(reviewed)]),
        ("negatives", [PYTHON, "scripts/export_onboarding_stable_negatives.py", "--event-proposals", str(proposals), "--work-dir", str(work / "negatives"), "--out-dir", str(hard_negatives_dir), "--force"]),
        ("dataset", [PYTHON, "scripts/assemble_active_panel_dataset.py", "--reviewed-label-manifest", str(reviewed), "--hard-negative-export", str(hard_negatives_dir / "hard_negative_export.json"), "--out-dir", str(dataset_dir), "--force"]),
        ("train", [PYTHON, "scripts/run_yolo26_training_eval.py", "--data-yaml", str(dataset_dir / "data.yaml"), "--dataset-manifest", str(dataset_dir / "dataset_manifest.json"), "--base-model", str(args.base_model), "--train-project", str(work / "train"), "--train-name", "model", "--epochs", str(args.epochs), "--device", args.device, "--execute-training", "--output", str(training_report), "--force"]),
        ("publish", [PYTHON, "-c", "import json,shutil,sys;from pathlib import Path;report=json.loads(Path(sys.argv[1]).read_text());src=Path(report['trained_model_path']);dst=Path(sys.argv[2]);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);print('published',dst)", str(training_report), str(trained_model)]),
    ]
    for name, command in stages:
        run_stage(name, command)
        if name == "proposals":
            cap = cap_event_proposals(
                proposals,
                max_events=args.max_teacher_events,
                proposal_mode=args.proposal_mode,
                teacher_negative_cap=args.teacher_negative_cap,
            )
            print(json.dumps({"stage": "proposal_cap", **cap}), flush=True)
        if name == "teacher":
            appended = append_local_negative_labels(teacher_labels_path=teacher_labels, proposals_path=proposals)
            if appended:
                print(json.dumps({"stage": "local_negative_labels", "label_count": appended}), flush=True)

    print(json.dumps({
        "status": "trained",
        "trained_model": str(trained_model),
        "exam_clip": str(split["exam_clip"]),
        "next": "scrub exam_clip, collect placement times, then scripts/build_day1_exam_gate.py",
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
