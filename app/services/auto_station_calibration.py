from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "factory-vision-auto-station-calibration-v1"
GENERATED_BY = "auto_station_calibration_v1"

OUTPUT_MARGIN_RATIO = 0.10  # linear expansion of the landing-union box, fraction of frame size
MOTION_SAMPLE_FPS = 0.5
MOTION_PERCENTILE = 75.0

FrameProvider = Callable[[Path, float], Any]


def derive_station_calibration(
    *,
    auto_boxes_path: Path,
    train_clip_path: Path,
    output_path: Path,
    frame_provider: FrameProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Derive runtime calibration zones from train-portion evidence only.

    Output zone: union of the auto-label landing boxes (where teacher-verified parts came to
    rest). Source zone: the busiest residual-motion region outside the output zone (where the
    worker and machine produce parts). No truth ledger is read here.
    """
    if output_path.exists() and not force:
        raise FileExistsError(output_path)
    auto_boxes = json.loads(auto_boxes_path.read_text(encoding="utf-8"))
    labels = list(auto_boxes.get("labels") or [])
    if not labels:
        raise ValueError("auto-box manifest has no labels; cannot derive an output zone")

    width = int(labels[0]["image_width"])
    height = int(labels[0]["image_height"])
    landing_union = _union_box([label["box"] for label in labels])
    output_box = _expand_box(landing_union, width=width, height=height,
                             dx=width * OUTPUT_MARGIN_RATIO, dy=height * OUTPUT_MARGIN_RATIO)

    reader = frame_provider or _default_frame_provider()
    source_box = _busiest_region_outside(
        train_clip_path,
        reader=reader,
        exclude_box=output_box,
        width=width,
        height=height,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "station_id": auto_boxes.get("station_id"),
        "source_auto_boxes_path": str(auto_boxes_path),
        "source_train_clip_path": str(train_clip_path),
        "frame_width": width,
        "frame_height": height,
        "source_polygons": [_box_polygon(source_box)],
        "output_polygons": [_box_polygon(output_box)],
        "ignore_polygons": [],
        "gate": None,
        "derivation": {
            "output_zone": "union_of_teacher_verified_landing_boxes_plus_margin",
            "source_zone": "busiest_motion_region_outside_output_zone",
            "output_margin_ratio": OUTPUT_MARGIN_RATIO,
            "motion_sample_fps": MOTION_SAMPLE_FPS,
        },
        "label_authority_tier": "bronze",
        "refuses_validation_truth": True,
        "validation_truth_eligible": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _busiest_region_outside(
    train_clip_path: Path,
    *,
    reader: FrameProvider,
    exclude_box: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    duration = _video_duration_sec(train_clip_path)
    step = 1.0 / MOTION_SAMPLE_FPS
    accumulator: Any = None
    previous = None
    timestamp = 0.0
    while timestamp < max(step, duration - step):
        try:
            frame = reader(train_clip_path, round(timestamp, 3))
        except Exception:  # noqa: BLE001 - sparse sampling tolerates unreadable frames
            timestamp += step
            continue
        gray = cv2.cvtColor(cv2.resize(frame, (max(2, width // 4), max(2, height // 4))), cv2.COLOR_BGR2GRAY)
        if previous is not None:
            diff = cv2.absdiff(previous, gray).astype("float32")
            accumulator = diff if accumulator is None else accumulator + diff
        previous = gray
        timestamp += step

    fallback = _largest_strip_outside(exclude_box, width=width, height=height)
    if accumulator is None:
        return fallback
    scale_x = width / accumulator.shape[1]
    scale_y = height / accumulator.shape[0]
    x1, y1, x2, y2 = exclude_box
    accumulator[int(y1 / scale_y) : int(y2 / scale_y) + 1, int(x1 / scale_x) : int(x2 / scale_x) + 1] = 0.0
    nonzero = accumulator[accumulator > 0]
    if nonzero.size == 0:
        return fallback
    threshold = float(np.percentile(nonzero, MOTION_PERCENTILE))
    mask = (accumulator >= threshold).astype("uint8") * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return fallback
    largest = max(contours, key=cv2.contourArea)
    bx, by, bw, bh = cv2.boundingRect(largest)
    box = (bx * scale_x, by * scale_y, (bx + bw) * scale_x, (by + bh) * scale_y)
    if (box[2] - box[0]) < width * 0.02 or (box[3] - box[1]) < height * 0.02:
        return fallback
    return box


def _largest_strip_outside(
    exclude_box: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = exclude_box
    strips = [
        (0.0, 0.0, x1, float(height)),  # left of the output zone
        (x2, 0.0, float(width), float(height)),  # right
        (0.0, 0.0, float(width), y1),  # above
        (0.0, y2, float(width), float(height)),  # below
    ]
    return max(strips, key=lambda box: max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1]))


def _union_box(boxes: list[list[float]]) -> tuple[float, float, float, float]:
    return (
        min(float(box[0]) for box in boxes),
        min(float(box[1]) for box in boxes),
        max(float(box[2]) for box in boxes),
        max(float(box[3]) for box in boxes),
    )


def _expand_box(
    box: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
    dx: float,
    dy: float,
) -> tuple[float, float, float, float]:
    return (
        max(0.0, box[0] - dx),
        max(0.0, box[1] - dy),
        min(float(width), box[2] + dx),
        min(float(height), box[3] + dy),
    )


def _box_polygon(box: tuple[float, float, float, float]) -> list[list[float]]:
    x1, y1, x2, y2 = (round(float(value), 1) for value in box)
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _video_duration_sec(video_path: Path) -> float:
    import cv2  # noqa: PLC0415

    capture = cv2.VideoCapture(str(video_path))
    try:
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        capture.release()
    if frame_count <= 0.0 or fps <= 0.0:
        return 0.0
    return frame_count / fps


def _default_frame_provider() -> FrameProvider:
    def _read(video_path: Path, timestamp_sec: float) -> Any:
        import cv2  # noqa: PLC0415

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"could not open video: {video_path}")
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise RuntimeError(f"could not read frame at {timestamp_sec:.3f}s from {video_path}")
        return frame

    return _read
