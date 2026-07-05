#!/usr/bin/env python3
"""Build a diagnostic-only IMG_2628 active-placement YOLO dataset.

This intentionally does not promote IMG_2628 truth. It creates an engineering
dataset for local detector diagnostics from the current Codex visual draft plus
hard negatives around rejected/static moments.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

import cv2


SCHEMA_VERSION = "img2628-diagnostic-active-panel-yolo-dataset-v1"
DEFAULT_WORKSHEET = Path("data/reports/img2628_codex_visual_review_worksheet.draft_v1.csv")
DEFAULT_VIDEO = Path("data/videos/from-pc/IMG_2628.MOV")
DEFAULT_OUT_DIR = Path("data/labels/active_panel_img2628_diagnostic_v1")
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080
POSITIVE_BOX_XYXY = [900, 350, 1920, 1080]


def safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


def yolo_line_from_xyxy(box: list[float], *, width: int = IMAGE_WIDTH, height: int = IMAGE_HEIGHT) -> str:
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


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_video_metadata(video_path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        capture.release()
    duration = frame_count / fps if fps > 0 else None
    return {"frame_count": frame_count, "fps": fps, "width": width, "height": height, "duration": duration}


def read_frame_at(capture: cv2.VideoCapture, timestamp: float) -> Any:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
    ok, frame = capture.read()
    if not ok or frame is None:
        raise RuntimeError(f"could not read frame at {timestamp:.3f}s")
    return frame


def split_for_index(index: int) -> str:
    return "val" if index % 5 == 0 else "train"


def add_item(
    *,
    items: list[dict[str, Any]],
    capture: cv2.VideoCapture,
    out_dir: Path,
    index: int,
    timestamp: float,
    kind: str,
    source_id: str,
    reason: str,
    box: list[int] | None,
) -> None:
    split = split_for_index(index)
    stem = f"{kind}-{index:06d}-t{timestamp:08.2f}-{safe_stem(source_id)}"
    image_path = out_dir / "images" / split / f"{stem}.jpg"
    label_path = out_dir / "labels" / split / f"{stem}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    frame = read_frame_at(capture, timestamp)
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"could not write image: {image_path}")
    label_path.write_text((yolo_line_from_xyxy([float(v) for v in box]) + "\n") if box else "", encoding="utf-8")
    items.append(
        {
            "kind": "positive" if box else "hard_negative",
            "timestamp_seconds": round(timestamp, 3),
            "source_id": source_id,
            "reason": reason,
            "box": box,
            "split": split,
            "image_path": image_path.as_posix(),
            "label_path": label_path.as_posix(),
        }
    )


def far_from_accepted_windows(timestamp: float, accepted_events: list[float]) -> bool:
    for event_ts in accepted_events:
        if event_ts - 16.0 <= timestamp <= event_ts + 12.0:
            return False
    return True


def build_dataset(*, worksheet: Path, video: Path, out_dir: Path, force: bool) -> Path:
    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} exists; pass --force")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(worksheet)
    metadata = read_video_metadata(video)
    duration = float(metadata["duration"] or 0.0)
    accepted = [
        row
        for row in rows
        if (row.get("human_decision_accept_countable") or "").strip().lower() == "yes"
        and (row.get("exact_event_ts") or "").strip()
    ]
    rejected = [row for row in rows if (row.get("human_decision_accept_countable") or "").strip().lower() == "no"]
    accepted_events = [float(row["exact_event_ts"]) for row in accepted]
    items: list[dict[str, Any]] = []

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video}")
    try:
        item_index = 1

        for event_index, row in enumerate(accepted, start=1):
            event_ts = float(row["exact_event_ts"])
            for offset in (-8.0, -6.0, -4.0, -2.0, 0.0):
                timestamp = max(0.0, event_ts + offset)
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=timestamp,
                    kind="pos",
                    source_id=f"{row['truth_event_id_if_accepted']}-offset{offset:g}",
                    reason="diagnostic_positive_pre_completion_output_placement_window",
                    box=list(POSITIVE_BOX_XYXY),
                )
                item_index += 1

            for offset in (4.0, 8.0):
                timestamp = min(duration, event_ts + offset)
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=timestamp,
                    kind="neg",
                    source_id=f"{row['truth_event_id_if_accepted']}-post{offset:g}",
                    reason="post_completion_static_output_negative",
                    box=None,
                )
                item_index += 1

        for row in rejected:
            source_id = row.get("candidate_id") or "rejected"
            center = float(row.get("draft_center_ts_sec") or row.get("window_start_sec") or 0.0)
            for offset in (-2.0, 0.0, 2.0):
                timestamp = min(duration, max(0.0, center + offset))
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=timestamp,
                    kind="neg",
                    source_id=f"{source_id}-offset{offset:g}",
                    reason="rejected_cv_motion_candidate_negative",
                    box=None,
                )
                item_index += 1

        uniform_count = 140
        if duration > 0:
            for uniform_index in range(uniform_count):
                timestamp = ((uniform_index + 0.5) / uniform_count) * duration
                if not far_from_accepted_windows(timestamp, accepted_events):
                    continue
                add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=timestamp,
                    kind="neg",
                    source_id=f"uniform-{uniform_index + 1:03d}",
                    reason="uniform_background_negative_far_from_draft_events",
                    box=None,
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
        "  0: active_panel\n",
        encoding="utf-8",
    )
    positive_count = sum(1 for item in items if item["kind"] == "positive")
    negative_count = len(items) - positive_count
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "case_id": "img2628",
        "video_path": video.as_posix(),
        "worksheet": worksheet.as_posix(),
        "data_yaml_path": data_yaml.as_posix(),
        "diagnostic_only": True,
        "validation_truth_eligible": False,
        "training_eligible_for_promotion": False,
        "label_source": "codex_visual_draft_and_diagnostic_hard_negatives_not_human_reviewed",
        "class_names": ["active_panel"],
        "positive_box_xyxy": POSITIVE_BOX_XYXY,
        "video_metadata": metadata,
        "summary": {
            "accepted_draft_event_count": len(accepted),
            "rejected_candidate_count": len(rejected),
            "positive_images": positive_count,
            "hard_negative_images": negative_count,
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
    parser = argparse.ArgumentParser(description="Build diagnostic-only IMG_2628 active-panel YOLO dataset")
    parser.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = build_dataset(worksheet=args.worksheet, video=args.video, out_dir=args.out_dir, force=args.force)
    print(json.dumps({"dataset_manifest": manifest_path.as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
