#!/usr/bin/env python3
"""Build a diagnostic-only IMG_2628 event detector dataset from motion windows.

The source labels are not validation truth. This is an engineering dataset for
local app diagnostics: the 25 highest-confidence motion windows are treated as
positive event windows because the only reviewed hard reference currently
available for IMG_2628 is the total count of 25.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

import cv2


SCHEMA_VERSION = "img2628-motion-score-event-yolo-dataset-v1"
DEFAULT_WORKSHEET = Path("data/reports/img2628_codex_visual_review_worksheet.draft_v1.csv")
DEFAULT_VIDEO = Path("data/videos/from-pc/IMG_2628.MOV")
DEFAULT_OUT_DIR = Path("data/labels/img2628_motion_score_event_diagnostic_v1")
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080
EVENT_BOX_XYXY = [250, 300, 1200, 940]


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


def _yolo_line_from_xyxy(box: list[float]) -> str:
    x1, y1, x2, y2 = [float(value) for value in box]
    cx = ((x1 + x2) / 2.0) / IMAGE_WIDTH
    cy = ((y1 + y2) / 2.0) / IMAGE_HEIGHT
    width = (x2 - x1) / IMAGE_WIDTH
    height = (y2 - y1) / IMAGE_HEIGHT
    return f"0 {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}"


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_video_metadata(video_path: Path) -> dict[str, Any]:
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
    return {
        "frame_count": frame_count,
        "fps": fps,
        "width": width,
        "height": height,
        "duration": frame_count / fps if fps > 0 else None,
    }


def _read_frame_at(capture: cv2.VideoCapture, timestamp: float) -> Any:
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
    ok, frame = capture.read()
    if not ok or frame is None:
        raise RuntimeError(f"could not read frame at {timestamp:.3f}s")
    return frame


def _split(index: int) -> str:
    return "val" if index % 5 == 0 else "train"


def _add_item(
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
    split = _split(index)
    stem = f"{kind}-{index:06d}-t{timestamp:08.2f}-{_safe_stem(source_id)}"
    image_path = out_dir / "images" / split / f"{stem}.jpg"
    label_path = out_dir / "labels" / split / f"{stem}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _read_frame_at(capture, timestamp)
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"could not write image: {image_path}")
    label_path.write_text((_yolo_line_from_xyxy([float(value) for value in box]) + "\n") if box else "", encoding="utf-8")
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


def _far_from_positive(timestamp: float, positive_centers: list[float]) -> bool:
    return all(abs(timestamp - center) > 18.0 for center in positive_centers)


def build_dataset(*, worksheet: Path, video: Path, out_dir: Path, expected_total: int, selection: str, force: bool) -> Path:
    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} exists; pass --force")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(worksheet)
    if selection == "worksheet_accept":
        positive_ids = {
            row["candidate_id"]
            for row in rows
            if (row.get("human_decision_accept_countable") or "").strip().lower() == "yes"
        }
        if len(positive_ids) != expected_total:
            raise ValueError(f"worksheet_accept selected {len(positive_ids)} positives, expected {expected_total}")
    elif selection == "top_motion":
        sorted_rows = sorted(rows, key=lambda row: float(row.get("motion_score") or 0.0), reverse=True)
        positive_ids = {row["candidate_id"] for row in sorted_rows[:expected_total]}
    else:
        raise ValueError(f"unknown selection: {selection}")
    positive_rows = [row for row in rows if row["candidate_id"] in positive_ids]
    negative_rows = [row for row in rows if row["candidate_id"] not in positive_ids]
    positive_centers = [float(row["draft_center_ts_sec"]) for row in positive_rows]
    metadata = _read_video_metadata(video)
    duration = float(metadata.get("duration") or 0.0)

    items: list[dict[str, Any]] = []
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video}")
    try:
        item_index = 1
        for row in positive_rows:
            center = float(row["draft_center_ts_sec"])
            for offset in (-5.0, -3.0, -1.0, 1.0):
                _add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=min(duration, max(0.0, center + offset)),
                    kind="pos",
                    source_id=f"{row['candidate_id']}-offset{offset:g}",
                    reason="diagnostic_positive_top_25_motion_window",
                    box=list(EVENT_BOX_XYXY),
                )
                item_index += 1
            for offset in (6.0, 10.0):
                _add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=min(duration, max(0.0, center + offset)),
                    kind="neg",
                    source_id=f"{row['candidate_id']}-post{offset:g}",
                    reason="post_event_negative",
                    box=None,
                )
                item_index += 1

        for row in negative_rows:
            center = float(row["draft_center_ts_sec"])
            for offset in (-3.0, 0.0, 3.0):
                _add_item(
                    items=items,
                    capture=capture,
                    out_dir=out_dir,
                    index=item_index,
                    timestamp=min(duration, max(0.0, center + offset)),
                    kind="neg",
                    source_id=f"{row['candidate_id']}-offset{offset:g}",
                    reason="lower_rank_motion_window_negative",
                    box=None,
                )
                item_index += 1

        for uniform_index in range(120):
            timestamp = ((uniform_index + 0.5) / 120.0) * duration
            if not _far_from_positive(timestamp, positive_centers):
                continue
            _add_item(
                items=items,
                capture=capture,
                out_dir=out_dir,
                index=item_index,
                timestamp=timestamp,
                kind="neg",
                source_id=f"uniform-{uniform_index + 1:03d}",
                reason="uniform_background_negative_far_from_top_motion_windows",
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
        "  0: img2628_count_event\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "case_id": "img2628",
        "video_path": video.as_posix(),
        "worksheet": worksheet.as_posix(),
        "data_yaml_path": data_yaml.as_posix(),
        "diagnostic_only": True,
        "validation_truth_eligible": False,
        "training_eligible_for_promotion": False,
        "label_source": f"{selection}_total_25_diagnostic_not_human_reviewed",
        "selection": selection,
        "expected_total_used_for_positive_selection": expected_total,
        "positive_box_xyxy": EVENT_BOX_XYXY,
        "positive_candidate_ids": [row["candidate_id"] for row in positive_rows],
        "negative_candidate_ids": [row["candidate_id"] for row in negative_rows],
        "video_metadata": metadata,
        "summary": {
            "positive_candidate_count": len(positive_rows),
            "negative_candidate_count": len(negative_rows),
            "positive_images": sum(1 for item in items if item["kind"] == "positive"),
            "hard_negative_images": sum(1 for item in items if item["kind"] == "hard_negative"),
            "total_images": len(items),
        },
        "items": items,
    }
    manifest_path = out_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build IMG_2628 motion-score diagnostic YOLO dataset")
    parser.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--expected-total", type=int, default=25)
    parser.add_argument("--selection", choices=["top_motion", "worksheet_accept"], default="top_motion")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = build_dataset(
        worksheet=args.worksheet,
        video=args.video,
        out_dir=args.out_dir,
        expected_total=args.expected_total,
        selection=args.selection,
        force=args.force,
    )
    print(json.dumps({"manifest": str(manifest)}))


if __name__ == "__main__":
    main()
