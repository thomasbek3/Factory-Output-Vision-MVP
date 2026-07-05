#!/usr/bin/env python3
"""Build a diagnostic-only real_factory active-placement YOLO dataset.

The labels produced here are engineering labels for local runtime debugging.
They are not validation truth and must not be promoted into the verification
registry without reviewed timestamp truth.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cv2


SCHEMA_VERSION = "real-factory-diagnostic-active-placement-yolo-dataset-v1"
DEFAULT_DRAFT = Path("data/reports/active_learning/real_factory_codex_visual_count_draft.v1.json")
DEFAULT_LEARNING_PACKET = Path("data/reports/active_learning/real_factory_failed_blind_run_learning_packet.v1.json")
DEFAULT_VIDEO = Path("data/videos/from-pc/real_factory.MOV")
DEFAULT_OUT_DIR = Path("data/labels/real_factory_diagnostic_action_v1")
DEFAULT_RUNTIME_DIAGNOSTICS = [
    Path(
        "data/reports/real_factory_app_observed_events.run8092.img2628_wirebase_conf040_"
        "cluster250_age52_min12_debounce60_speed8_diag_v1.json"
    ),
    Path(
        "data/reports/real_factory_app_observed_events.run8092.img2628_wirebase_conf045_"
        "cluster250_age52_min12_debounce60_speed8_diag_v1.json"
    ),
    Path(
        "data/reports/real_factory_app_observed_events.run8092.img2628_wirebase_conf050_"
        "cluster250_age52_min12_debounce60_speed8_diag_v1.json"
    ),
]
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080

# Hand-boxed engineering regions around the active placement/carry action in
# the four bronze visual draft windows. Keep these tight to the handled panel
# and worker interaction; broad boxes over static stacks teach a static
# background detector and break event counting.
POSITIVE_BOXES_XYXY_BY_EVENT_ID = {
    "real_factory_codex_draft_0001": [790, 250, 1430, 760],
    "real_factory_codex_draft_0002": [1020, 260, 1860, 890],
    "real_factory_codex_draft_0003": [650, 270, 1270, 900],
    "real_factory_codex_draft_0004": [560, 330, 1260, 850],
}
POSITIVE_OFFSETS_SEC = [-7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0]
POST_EVENT_NEGATIVE_OFFSETS_SEC = [8.0, 12.0, 18.0]
ANCHOR_EXCLUSION_RADIUS_SEC = 28.0


def safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


def scale_box_xyxy(box: list[float], *, width: int, height: int) -> list[float]:
    x_scale = width / REFERENCE_WIDTH
    y_scale = height / REFERENCE_HEIGHT
    return [box[0] * x_scale, box[1] * y_scale, box[2] * x_scale, box[3] * y_scale]


def yolo_line_from_xyxy(box: list[float], *, width: int, height: int) -> str:
    x1, y1, x2, y2 = [float(value) for value in box]
    x1 = max(0.0, min(float(width), x1))
    x2 = max(0.0, min(float(width), x2))
    y1 = max(0.0, min(float(height), y1))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"degenerate box after clipping: {box}")
    cx = ((x1 + x2) / 2.0) / width
    cy = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def ffprobe_metadata(video_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height,avg_frame_rate,nb_frames",
            "-select_streams",
            "v:0",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [{}])[0]
    duration = float((payload.get("format") or {}).get("duration") or 0.0)
    return {
        "duration_sec": duration,
        "width": int(stream.get("width") or REFERENCE_WIDTH),
        "height": int(stream.get("height") or REFERENCE_HEIGHT),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
    }


def read_frame_at(capture: cv2.VideoCapture, timestamp_sec: float) -> Any:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
    ok, frame = capture.read()
    if not ok or frame is None:
        raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s")
    return frame


def load_draft_events(draft_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    events = list(payload.get("draft_events") or [])
    if not events:
        raise ValueError(f"no draft_events found in {draft_path}")
    return sorted(events, key=lambda item: float(item["event_ts"]))


def timestamp_is_far_from_anchors(timestamp: float, anchors: list[float], *, radius_sec: float = ANCHOR_EXCLUSION_RADIUS_SEC) -> bool:
    return all(abs(timestamp - anchor) > radius_sec for anchor in anchors)


def load_learning_negative_timestamps(packet_path: Path, anchors: list[float]) -> list[dict[str, Any]]:
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    for item in payload.get("false_positive_candidates") or []:
        timestamp = float(item.get("event_ts") or 0.0)
        if timestamp_is_far_from_anchors(timestamp, anchors):
            candidates.append(
                {
                    "timestamp_seconds": timestamp,
                    "source_id": str(item.get("candidate_id") or "false-positive"),
                    "reason": "failed_blind_runtime_false_positive_hard_negative",
                }
            )
    for item in payload.get("motion_window_candidates") or []:
        timestamp = float(item.get("center_timestamp") or 0.0)
        if timestamp_is_far_from_anchors(timestamp, anchors):
            candidates.append(
                {
                    "timestamp_seconds": timestamp,
                    "source_id": str(item.get("candidate_id") or item.get("motion_event_id") or "motion-window"),
                    "reason": "blind_motion_window_far_from_draft_anchor_negative",
                }
            )
    return dedupe_negative_candidates(candidates)


def load_runtime_negative_timestamps(paths: list[Path], anchors: list[float]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("events") or []:
            if str(item.get("reason") or "") != "dead_track_event":
                continue
            timestamp = float(item.get("event_ts") or 0.0)
            if timestamp_is_far_from_anchors(timestamp, anchors):
                candidates.append(
                    {
                        "timestamp_seconds": timestamp,
                        "source_id": f"{path.stem}-track-{item.get('track_id', 'unknown')}",
                        "reason": "local_runtime_overcount_hard_negative",
                    }
                )
    return dedupe_negative_candidates(candidates)


def dedupe_negative_candidates(candidates: list[dict[str, Any]], *, min_gap_sec: float = 6.0) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: float(item["timestamp_seconds"])):
        timestamp = float(candidate["timestamp_seconds"])
        if output and abs(timestamp - float(output[-1]["timestamp_seconds"])) < min_gap_sec:
            continue
        output.append(candidate)
    return output


def split_for_index(index: int) -> str:
    return "val" if index % 5 == 0 else "train"


def add_item(
    *,
    items: list[dict[str, Any]],
    capture: cv2.VideoCapture,
    out_dir: Path,
    index: int,
    timestamp: float,
    duration: float,
    kind: str,
    source_id: str,
    reason: str,
    width: int,
    height: int,
    box_xyxy: list[float] | None,
) -> None:
    timestamp = min(duration, max(0.0, timestamp))
    split = split_for_index(index)
    stem = f"{kind}-{index:06d}-t{timestamp:08.2f}-{safe_stem(source_id)}"
    image_path = out_dir / "images" / split / f"{stem}.jpg"
    label_path = out_dir / "labels" / split / f"{stem}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    frame = read_frame_at(capture, timestamp)
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"could not write image: {image_path}")
    label_text = ""
    if box_xyxy is not None:
        label_text = yolo_line_from_xyxy(box_xyxy, width=width, height=height) + "\n"
    label_path.write_text(label_text, encoding="utf-8")
    items.append(
        {
            "kind": "positive" if box_xyxy is not None else "hard_negative",
            "timestamp_seconds": round(timestamp, 3),
            "source_id": source_id,
            "reason": reason,
            "box_xyxy": None if box_xyxy is None else [round(float(value), 3) for value in box_xyxy],
            "split": split,
            "image_path": image_path.as_posix(),
            "label_path": label_path.as_posix(),
        }
    )


def build_dataset(
    *,
    draft_path: Path,
    learning_packet_path: Path,
    video_path: Path,
    runtime_diagnostic_paths: list[Path],
    out_dir: Path,
    force: bool,
    uniform_negative_count: int,
) -> Path:
    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} exists; pass --force")
    out_dir.mkdir(parents=True, exist_ok=True)

    draft_events = load_draft_events(draft_path)
    anchors = [float(item["event_ts"]) for item in draft_events]
    metadata = ffprobe_metadata(video_path)
    duration = float(metadata["duration_sec"])
    width = int(metadata["width"])
    height = int(metadata["height"])

    items: list[dict[str, Any]] = []
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    try:
        item_index = 1
        for event in draft_events:
            event_id = str(event["draft_event_id"])
            anchor = float(event["event_ts"])
            ref_box = POSITIVE_BOXES_XYXY_BY_EVENT_ID.get(event_id)
            if ref_box is None:
                raise KeyError(f"missing positive box for {event_id}")
            box = scale_box_xyxy([float(value) for value in ref_box], width=width, height=height)
            for offset in POSITIVE_OFFSETS_SEC:
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=anchor + offset,
                    duration=duration,
                    kind="pos",
                    source_id=f"{event_id}-offset{offset:g}",
                    reason="bronze_draft_anchor_active_placement_debug_positive_not_truth",
                    width=width,
                    height=height,
                    box_xyxy=box,
                )
                item_index += 1
            for offset in POST_EVENT_NEGATIVE_OFFSETS_SEC:
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=anchor + offset,
                    duration=duration,
                    kind="neg",
                    source_id=f"{event_id}-post{offset:g}",
                    reason="post_anchor_static_or_recovery_negative",
                    width=width,
                    height=height,
                    box_xyxy=None,
                )
                item_index += 1

        negatives = load_learning_negative_timestamps(learning_packet_path, anchors)
        negatives.extend(load_runtime_negative_timestamps(runtime_diagnostic_paths, anchors))
        negatives = dedupe_negative_candidates(negatives)
        for candidate in negatives:
            for offset in (-2.0, 0.0, 2.0):
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=float(candidate["timestamp_seconds"]) + offset,
                    duration=duration,
                    kind="neg",
                    source_id=f"{candidate['source_id']}-offset{offset:g}",
                    reason=str(candidate["reason"]),
                    width=width,
                    height=height,
                    box_xyxy=None,
                )
                item_index += 1

        for uniform_index in range(max(0, uniform_negative_count)):
            timestamp = ((uniform_index + 0.5) / uniform_negative_count) * duration if uniform_negative_count else 0.0
            if not timestamp_is_far_from_anchors(timestamp, anchors):
                continue
            add_item(
                items=items,
                capture=capture,
                out_dir=out_dir,
                index=item_index,
                timestamp=timestamp,
                duration=duration,
                kind="neg",
                source_id=f"uniform-{uniform_index + 1:03d}",
                reason="uniform_background_negative_far_from_draft_anchors",
                width=width,
                height=height,
                box_xyxy=None,
            )
            item_index += 1
    finally:
        capture.release()

    data_yaml = out_dir / "data.yaml"
    data_yaml.write_text(
        f"path: {out_dir.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: real_factory_active_placement\n",
        encoding="utf-8",
    )
    positive_count = sum(1 for item in items if item["kind"] == "positive")
    hard_negative_count = len(items) - positive_count
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "case_id": "real_factory",
        "video_path": video_path.as_posix(),
        "draft_path": draft_path.as_posix(),
        "learning_packet_path": learning_packet_path.as_posix(),
        "runtime_diagnostic_paths": [path.as_posix() for path in runtime_diagnostic_paths if path.exists()],
        "data_yaml_path": data_yaml.as_posix(),
        "diagnostic_only": True,
        "validation_truth_eligible": False,
        "training_eligible_for_promotion": False,
        "label_source": "bronze_visual_draft_anchors_and_local_hard_negatives_not_validation_truth",
        "authority_boundary": (
            "Uses draft anchors only as engineering/debug navigation labels; "
            "does not create reviewed timestamp truth or registry promotion evidence."
        ),
        "positive_offsets_sec": POSITIVE_OFFSETS_SEC,
        "post_event_negative_offsets_sec": POST_EVENT_NEGATIVE_OFFSETS_SEC,
        "anchor_exclusion_radius_sec": ANCHOR_EXCLUSION_RADIUS_SEC,
        "positive_boxes_reference_xyxy": POSITIVE_BOXES_XYXY_BY_EVENT_ID,
        "draft_event_timestamps_sec": anchors,
        "video_metadata": metadata,
        "summary": {
            "draft_event_count": len(draft_events),
            "positive_images": positive_count,
            "hard_negative_images": hard_negative_count,
            "total_images": len(items),
            "train_images": sum(1 for item in items if item["split"] == "train"),
            "val_images": sum(1 for item in items if item["split"] == "val"),
        },
        "items": items,
    }
    manifest_path = out_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build real_factory diagnostic active-placement YOLO dataset")
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--learning-packet", type=Path, default=DEFAULT_LEARNING_PACKET)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--runtime-diagnostic", type=Path, action="append", default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--uniform-negative-count", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_diagnostics = DEFAULT_RUNTIME_DIAGNOSTICS if args.runtime_diagnostic is None else args.runtime_diagnostic
    manifest_path = build_dataset(
        draft_path=args.draft,
        learning_packet_path=args.learning_packet,
        video_path=args.video,
        runtime_diagnostic_paths=list(runtime_diagnostics),
        out_dir=args.out_dir,
        force=args.force,
        uniform_negative_count=args.uniform_negative_count,
    )
    print(json.dumps({"dataset_manifest": manifest_path.as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
