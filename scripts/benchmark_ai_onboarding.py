#!/usr/bin/env python3
"""Benchmark blind AI-only station onboarding on a prerecorded video.

This script is an evaluation harness, not validation proof. It keeps held-out
truth out of onboarding inputs, builds teacher-consensus artifacts, optionally
evaluates a candidate detector on consensus labels, and writes one receipt-style
report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_detector_false_positives, eval_detector_positives

SCHEMA_VERSION = "factory-vision-ai-onboarding-benchmark-v1"
TEACHER_LABEL_SCHEMA_VERSION = "factory-vision-ai-onboarding-teacher-labels-v1"
CONSENSUS_SCHEMA_VERSION = "factory-vision-ai-onboarding-consensus-v1"
DATASET_SCHEMA_VERSION = "active-panel-yolo-dataset-v1"

TeacherRunner = Callable[..., dict[str, Any]]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return slug or "station"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def probe_video(video_path: Path) -> dict[str, Any]:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        capture.release()
    duration_sec = frame_count / fps if fps > 0 else None
    return {
        "path": _repo_rel(video_path),
        "sha256": sha256_file(video_path),
        "fps": fps if fps > 0 else None,
        "frame_count": frame_count,
        "duration_sec": duration_sec,
        "width": width or None,
        "height": height or None,
    }


def _sample_timestamps(*, duration_sec: float, sample_interval_sec: float, max_frames: int) -> list[float]:
    if duration_sec <= 0:
        return []
    if sample_interval_sec <= 0:
        raise ValueError("sample interval must be positive")
    if max_frames <= 0:
        raise ValueError("max frames must be positive")
    timestamps: list[float] = []
    timestamp = 0.0
    while timestamp < duration_sec and len(timestamps) < max_frames:
        timestamps.append(round(timestamp, 3))
        timestamp += sample_interval_sec
    return timestamps


def extract_sample_frames(
    *,
    video_path: Path,
    out_dir: Path,
    max_duration_sec: float,
    sample_interval_sec: float,
    max_frames: int,
    force: bool,
) -> list[dict[str, Any]]:
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = probe_video(video_path)
    duration = float(metadata.get("duration_sec") or 0.0)
    bounded_duration = min(duration, max_duration_sec) if max_duration_sec > 0 else duration
    timestamps = _sample_timestamps(
        duration_sec=bounded_duration,
        sample_interval_sec=sample_interval_sec,
        max_frames=max_frames,
    )
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")

    rows: list[dict[str, Any]] = []
    try:
        for index, timestamp in enumerate(timestamps, start=1):
            frame_path = out_dir / f"frame_{index:06d}_{int(timestamp * 1000):09d}ms.jpg"
            if frame_path.exists() and not force:
                raise FileExistsError(f"{frame_path} exists; pass --force")
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            ok, frame = capture.read()
            if not ok:
                continue
            height, width = frame.shape[:2]
            cv2.imwrite(str(frame_path), frame)
            rows.append(
                {
                    "frame_id": f"frame-{index:06d}",
                    "frame_path": _repo_rel(frame_path),
                    "timestamp_sec": timestamp,
                    "sha256": sha256_file(frame_path),
                    "width": width,
                    "height": height,
                }
            )
    finally:
        capture.release()
    return rows


def build_candidate_windows(
    *,
    frame_rows: list[dict[str, Any]],
    window_radius_sec: float,
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for index, frame in enumerate(frame_rows, start=1):
        center = float(frame["timestamp_sec"])
        windows.append(
            {
                "window_id": f"window-{index:06d}",
                "window_type": "sampled_onboarding_candidate",
                "time_window": {
                    "start_sec": max(0.0, round(center - window_radius_sec, 3)),
                    "center_sec": round(center, 3),
                    "end_sec": round(center + window_radius_sec, 3),
                },
                "frame_asset": {
                    "frame_id": frame["frame_id"],
                    "frame_path": frame["frame_path"],
                    "timestamp_sec": center,
                    "sha256": frame["sha256"],
                    "width": frame["width"],
                    "height": frame["height"],
                },
            }
        )
    return windows


def dry_run_teacher_label(*, teacher_id: str, window: dict[str, Any]) -> dict[str, Any]:
    return {
        "teacher_id": teacher_id,
        "window_id": window["window_id"],
        "event_type": "unclear",
        "countable": False,
        "event_ts": None,
        "box_xyxy": None,
        "confidence": 0.0,
        "rationale": "Dry-run teacher did not inspect the frame.",
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


def build_teacher_labels(
    *,
    windows: list[dict[str, Any]],
    teacher_provider: str,
    teacher_count: int,
    teacher_runner: TeacherRunner | None = None,
) -> dict[str, Any]:
    if teacher_count <= 0:
        raise ValueError("teacher count must be positive")
    if teacher_provider != "dry_run_fixture" and teacher_runner is None:
        raise ValueError(f"teacher provider {teacher_provider!r} requires an injected runner in this harness")
    runner = teacher_runner or dry_run_teacher_label
    labels: list[dict[str, Any]] = []
    for teacher_index in range(1, teacher_count + 1):
        teacher_id = f"{teacher_provider}-{teacher_index}"
        for window in windows:
            raw = runner(teacher_id=teacher_id, window=window)
            labels.append(normalize_teacher_label(raw, teacher_id=teacher_id, window=window))
    return {
        "schema_version": TEACHER_LABEL_SCHEMA_VERSION,
        "teacher_provider": teacher_provider,
        "teacher_count": teacher_count,
        "labels": labels,
        "refuses_validation_truth": True,
    }


def normalize_teacher_label(raw: dict[str, Any], *, teacher_id: str, window: dict[str, Any]) -> dict[str, Any]:
    event_type = str(raw.get("event_type") or "unclear")
    countable = bool(raw.get("countable")) and event_type == "completed_output_placement"
    confidence = _bounded_float(raw.get("confidence"), default=0.0)
    event_ts = raw.get("event_ts")
    if event_ts is not None:
        event_ts = float(event_ts)
    box = raw.get("box_xyxy")
    normalized_box = _normalize_box(box) if box is not None else None
    return {
        "teacher_id": str(raw.get("teacher_id") or teacher_id),
        "window_id": str(raw.get("window_id") or window["window_id"]),
        "frame_path": (window.get("frame_asset") or {}).get("frame_path"),
        "event_type": event_type,
        "countable": countable,
        "event_ts": event_ts,
        "box_xyxy": normalized_box,
        "confidence": confidence,
        "rationale": str(raw.get("rationale") or ""),
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


def build_consensus(
    *,
    teacher_labels: dict[str, Any],
    min_teacher_agreement: int,
    min_confidence: float,
    timestamp_tolerance_sec: float,
) -> dict[str, Any]:
    if min_teacher_agreement <= 0:
        raise ValueError("min teacher agreement must be positive")
    candidates = [
        label
        for label in teacher_labels.get("labels", [])
        if label.get("countable") is True
        and label.get("event_ts") is not None
        and label.get("box_xyxy") is not None
        and float(label.get("confidence") or 0.0) >= min_confidence
    ]
    candidates.sort(key=lambda item: float(item["event_ts"]))

    clusters: list[list[dict[str, Any]]] = []
    for label in candidates:
        event_ts = float(label["event_ts"])
        placed = False
        for cluster in clusters:
            center = sum(float(item["event_ts"]) for item in cluster) / len(cluster)
            if abs(event_ts - center) <= timestamp_tolerance_sec:
                cluster.append(label)
                placed = True
                break
        if not placed:
            clusters.append([label])

    events: list[dict[str, Any]] = []
    unclear_clusters = 0
    for cluster_index, cluster in enumerate(clusters, start=1):
        teachers = sorted({str(item["teacher_id"]) for item in cluster})
        if len(teachers) < min_teacher_agreement:
            unclear_clusters += 1
            continue
        boxes = [item["box_xyxy"] for item in cluster if item.get("box_xyxy") is not None]
        events.append(
            {
                "event_id": f"consensus-event-{len(events) + 1:06d}",
                "cluster_id": f"cluster-{cluster_index:06d}",
                "event_ts": round(sum(float(item["event_ts"]) for item in cluster) / len(cluster), 3),
                "teacher_agreement": len(teachers),
                "teacher_ids": teachers,
                "mean_confidence": round(sum(float(item["confidence"]) for item in cluster) / len(cluster), 4),
                "box_xyxy": _mean_box(boxes),
                "frame_path": cluster[0].get("frame_path"),
                "label_authority_tier": "silver",
                "validation_truth_eligible": False,
                "training_eligible": True,
            }
        )
    return {
        "schema_version": CONSENSUS_SCHEMA_VERSION,
        "min_teacher_agreement": min_teacher_agreement,
        "min_confidence": min_confidence,
        "timestamp_tolerance_sec": timestamp_tolerance_sec,
        "consensus_event_count": len(events),
        "unclear_cluster_count": unclear_clusters,
        "events": events,
        "refuses_validation_truth": True,
    }


def write_consensus_dataset(
    *,
    consensus: dict[str, Any],
    dataset_dir: Path,
    force: bool,
) -> dict[str, Any]:
    if dataset_dir.exists() and any(dataset_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{dataset_dir} exists and is not empty; pass --force")
        shutil.rmtree(dataset_dir)
    image_dir = dataset_dir / "images" / "train"
    label_dir = dataset_dir / "labels" / "train"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for index, event in enumerate(consensus.get("events", []), start=1):
        source_image = REPO_ROOT / str(event["frame_path"])
        if not source_image.exists():
            continue
        image_path = image_dir / f"positive_{index:06d}{source_image.suffix.lower() or '.jpg'}"
        label_path = label_dir / f"positive_{index:06d}.txt"
        shutil.copyfile(source_image, image_path)
        width, height = _image_size(image_path)
        label_path.write_text(_yolo_label_line(event["box_xyxy"], width=width, height=height) + "\n", encoding="utf-8")
        items.append(
            {
                "kind": "positive",
                "label_id": event["event_id"],
                "class_name": "active_panel",
                "image_path": image_path.as_posix(),
                "label_path": label_path.as_posix(),
                "source_frame_path": event["frame_path"],
                "source_event_ts": event["event_ts"],
                "label_authority_tier": event["label_authority_tier"],
                "validation_truth_eligible": False,
                "training_eligible": True,
                "split": "train",
            }
        )

    data_yaml = dataset_dir / "data.yaml"
    data_yaml.write_text("path: .\ntrain: images/train\nval: images/train\nnames:\n  0: active_panel\n", encoding="utf-8")
    manifest_path = dataset_dir / "dataset_manifest.json"
    manifest = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "label_source": "ai_teacher_consensus",
        "validation_truth_eligible": False,
        "training_eligible": bool(items),
        "items": items,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ready_for_training": bool(items),
        "positive_count": len(items),
        "data_yaml": data_yaml.as_posix(),
        "dataset_manifest": manifest_path.as_posix(),
    }


def evaluate_candidate_model(
    *,
    candidate_model: Path | None,
    dataset_info: dict[str, Any],
    report_dir: Path,
    confidence: float,
    force: bool,
) -> dict[str, Any]:
    if candidate_model is None:
        return {"status": "skipped_no_candidate_model"}
    if not dataset_info.get("ready_for_training"):
        return {"status": "skipped_no_consensus_dataset"}
    data_yaml = Path(str(dataset_info["data_yaml"]))
    positives_path = report_dir / "candidate_detector_positive_eval.json"
    false_positive_path = report_dir / "candidate_detector_false_positive_eval.json"
    positive_report = eval_detector_positives.evaluate_detector_positives(
        data_yaml=data_yaml,
        dataset_manifest=None,
        model_path=candidate_model,
        output_path=positives_path,
        confidence=confidence,
        force=force,
    )
    try:
        false_positive_report = eval_detector_false_positives.evaluate_false_positives(
            data_yaml=data_yaml,
            dataset_manifest=None,
            model_path=candidate_model,
            output_path=false_positive_path,
            confidence=confidence,
            force=force,
        )
        false_positive_summary = false_positive_report["summary"]
    except ValueError as exc:
        false_positive_summary = {"status": "skipped", "reason": str(exc)}
    return {
        "status": "evaluated",
        "candidate_model": candidate_model.as_posix(),
        "positive_eval_report": positives_path.as_posix(),
        "false_positive_eval_report": false_positive_path.as_posix(),
        "positive_summary": positive_report["summary"],
        "false_positive_summary": false_positive_summary,
    }


def build_holdout_grade(
    *,
    expected_total: int | None,
    consensus_count: int,
    tolerance: int,
    redact: bool,
) -> dict[str, Any]:
    if expected_total is None:
        return {"status": "not_provided", "expected_total_redacted": redact}
    delta = consensus_count - expected_total
    passed = abs(delta) <= tolerance
    payload: dict[str, Any] = {
        "status": "graded",
        "expected_total_redacted": redact,
        "within_tolerance": passed,
        "tolerance": tolerance,
    }
    if not redact:
        payload["expected_total"] = expected_total
        payload["consensus_count"] = consensus_count
        payload["delta"] = delta
    return payload


def decide_status(*, consensus_count: int, dataset_ready: bool, holdout_grade: dict[str, Any]) -> str:
    if consensus_count == 0:
        return "needs_real_teacher_or_more_footage"
    if not dataset_ready:
        return "needs_training_dataset"
    if holdout_grade.get("status") == "graded" and holdout_grade.get("within_tolerance") is False:
        return "fail_replay_or_consensus_mismatch"
    return "ready_for_training_or_replay_check"


def run_benchmark(
    *,
    video_path: Path,
    station_id: str,
    minutes: float,
    output: Path,
    work_dir: Path,
    teacher_provider: str,
    teacher_count: int,
    min_teacher_agreement: int,
    min_confidence: float,
    timestamp_tolerance_sec: float,
    sample_interval_sec: float,
    max_frames: int,
    candidate_model: Path | None,
    detector_confidence: float,
    held_out_expected_total: int | None,
    holdout_tolerance: int,
    redact_held_out_truth: bool,
    force: bool,
    teacher_runner: TeacherRunner | None = None,
) -> dict[str, Any]:
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if work_dir.exists() and any(work_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{work_dir} exists and is not empty; pass --force")
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    max_duration_sec = minutes * 60.0
    video = probe_video(video_path)
    frame_rows = extract_sample_frames(
        video_path=video_path,
        out_dir=work_dir / "frames",
        max_duration_sec=max_duration_sec,
        sample_interval_sec=sample_interval_sec,
        max_frames=max_frames,
        force=force,
    )
    windows = build_candidate_windows(frame_rows=frame_rows, window_radius_sec=2.0)
    teacher_labels = build_teacher_labels(
        windows=windows,
        teacher_provider=teacher_provider,
        teacher_count=teacher_count,
        teacher_runner=teacher_runner,
    )
    consensus = build_consensus(
        teacher_labels=teacher_labels,
        min_teacher_agreement=min_teacher_agreement,
        min_confidence=min_confidence,
        timestamp_tolerance_sec=timestamp_tolerance_sec,
    )
    dataset = write_consensus_dataset(
        consensus=consensus,
        dataset_dir=work_dir / "dataset",
        force=force,
    )
    candidate_eval = evaluate_candidate_model(
        candidate_model=candidate_model,
        dataset_info=dataset,
        report_dir=work_dir,
        confidence=detector_confidence,
        force=force,
    )
    holdout_grade = build_holdout_grade(
        expected_total=held_out_expected_total,
        consensus_count=int(consensus["consensus_event_count"]),
        tolerance=holdout_tolerance,
        redact=redact_held_out_truth,
    )
    status = decide_status(
        consensus_count=int(consensus["consensus_event_count"]),
        dataset_ready=bool(dataset["ready_for_training"]),
        holdout_grade=holdout_grade,
    )

    paths = {
        "frames_manifest": (work_dir / "frames_manifest.json").as_posix(),
        "candidate_windows": (work_dir / "candidate_windows.json").as_posix(),
        "teacher_labels": (work_dir / "teacher_labels.json").as_posix(),
        "consensus": (work_dir / "consensus.json").as_posix(),
        "dataset_manifest": dataset["dataset_manifest"],
    }
    write_json(Path(paths["frames_manifest"]), {"frames": frame_rows}, force=True)
    write_json(Path(paths["candidate_windows"]), {"windows": windows}, force=True)
    write_json(Path(paths["teacher_labels"]), teacher_labels, force=True)
    write_json(Path(paths["consensus"]), consensus, force=True)

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": round(time.time(), 3),
        "station_id": station_id,
        "status": status,
        "claim_boundary": "learning_library_only",
        "blind_boundary": {
            "held_out_truth_used_by_onboarding": False,
            "held_out_truth_used_only_for_final_grade": held_out_expected_total is not None,
            "expected_total_redacted": redact_held_out_truth,
        },
        "video": video,
        "sampling": {
            "requested_minutes": minutes,
            "sample_interval_sec": sample_interval_sec,
            "max_frames": max_frames,
            "frames_extracted": len(frame_rows),
            "candidate_windows": len(windows),
        },
        "teachers": {
            "provider": teacher_provider,
            "teacher_count": teacher_count,
            "min_teacher_agreement": min_teacher_agreement,
            "min_confidence": min_confidence,
            "timestamp_tolerance_sec": timestamp_tolerance_sec,
        },
        "consensus_summary": {
            "consensus_event_count": consensus["consensus_event_count"],
            "unclear_cluster_count": consensus["unclear_cluster_count"],
            "training_eligible": bool(dataset["ready_for_training"]),
            "validation_truth_eligible": False,
        },
        "dataset": dataset,
        "training": {
            "status": "skipped_by_harness",
            "reason": "first benchmark pass records blind labels and eval gates; training is a later explicit step",
        },
        "candidate_detector_eval": candidate_eval,
        "held_out_grade": holdout_grade,
        "paths": paths,
    }
    write_json(output, report, force=force)
    return report


def _image_size(path: Path) -> tuple[int, int]:
    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Unable to read image: {path}")
    height, width = image.shape[:2]
    return width, height


def _yolo_label_line(box_xyxy: list[float], *, width: int, height: int) -> str:
    x1, y1, x2, y2 = box_xyxy
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"0 {cx:.8f} {cy:.8f} {bw:.8f} {bh:.8f}"


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(0.0, min(1.0, parsed))


def _normalize_box(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    x1, y1, x2, y2 = [float(item) for item in value]
    if not all(math.isfinite(item) for item in (x1, y1, x2, y2)):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _mean_box(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        round(sum(box[index] for box in boxes) / len(boxes), 3)
        for index in range(4)
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark blind AI-only onboarding on a prerecorded video")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--minutes", type=float, default=20.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--teacher-provider", default="dry_run_fixture", choices=["dry_run_fixture"])
    parser.add_argument("--teacher-count", type=int, default=3)
    parser.add_argument("--min-teacher-agreement", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.75)
    parser.add_argument("--timestamp-tolerance-sec", type=float, default=2.0)
    parser.add_argument("--sample-interval-sec", type=float, default=10.0)
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--candidate-model", type=Path)
    parser.add_argument("--detector-confidence", type=float, default=0.25)
    parser.add_argument("--held-out-expected-total", type=int)
    parser.add_argument("--holdout-tolerance", type=int, default=1)
    parser.add_argument("--redact-held-out-truth", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    station_slug = safe_slug(args.station_id)
    work_dir = args.work_dir or Path("data/reports/onboarding") / station_slug / "work"
    try:
        report = run_benchmark(
            video_path=args.video,
            station_id=args.station_id,
            minutes=args.minutes,
            output=args.output,
            work_dir=work_dir,
            teacher_provider=args.teacher_provider,
            teacher_count=args.teacher_count,
            min_teacher_agreement=args.min_teacher_agreement,
            min_confidence=args.min_confidence,
            timestamp_tolerance_sec=args.timestamp_tolerance_sec,
            sample_interval_sec=args.sample_interval_sec,
            max_frames=args.max_frames,
            candidate_model=args.candidate_model,
            detector_confidence=args.detector_confidence,
            held_out_expected_total=args.held_out_expected_total,
            holdout_tolerance=args.holdout_tolerance,
            redact_held_out_truth=args.redact_held_out_truth,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "status": report["status"],
                "frames_extracted": report["sampling"]["frames_extracted"],
                "consensus_event_count": report["consensus_summary"]["consensus_event_count"],
                "held_out_grade_status": report["held_out_grade"]["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
