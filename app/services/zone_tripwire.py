from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from app.services.segment_paths import resolve_segment_path as _resolve_segment_path
from app.services.stream_recorder import validate_segment_manifest

ScoreMethod = Literal["tiled_absdiff", "tiled_ssim", "tiled_edge"]
TriggerMode = Literal["motion_burst", "quiet_state_diff", "person_visit"]
TripwireTrigger = Literal["person_presence", "pixel"]

SCHEMA_VERSION = "factory-vision-zone-tripwire-v2"
DEFAULT_GRID_SIZE = 8
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TripwireConfig:
    trigger: TripwireTrigger = "person_presence"
    sample_fps: float = 10.0
    grid_size: int = DEFAULT_GRID_SIZE
    score_method: ScoreMethod = "tiled_absdiff"
    burst_threshold: float = 0.10
    state_interval_sec: float = 3.0
    calm_threshold: float = 0.015
    state_threshold: float = 0.06
    min_flash_ratio: float = 1.5
    bracket_sec: float = 8.0
    min_cluster_gap_sec: float = 1.0
    include_motion_burst: bool = False
    person_conf: float = 0.35
    person_model: str = "yolov8m.pt"
    presence_gap_sec: float = 8.0
    episode_max_sec: float = 60.0
    trigger_zone_margin: float = 0.15
    episode_pad_sec: float = 2.0

    def validate(self) -> None:
        if self.trigger not in {"person_presence", "pixel"}:
            raise ValueError("unsupported trigger")
        if self.sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        if self.grid_size <= 0:
            raise ValueError("grid_size must be positive")
        if self.score_method not in {"tiled_absdiff", "tiled_ssim", "tiled_edge"}:
            raise ValueError("unsupported score_method")
        if self.burst_threshold <= 0:
            raise ValueError("burst_threshold must be positive")
        if self.state_interval_sec <= 0:
            raise ValueError("state_interval_sec must be positive")
        if self.calm_threshold < 0:
            raise ValueError("calm_threshold must be non-negative")
        if self.state_threshold <= 0:
            raise ValueError("state_threshold must be positive")
        if self.min_flash_ratio <= 0:
            raise ValueError("min_flash_ratio must be positive")
        if self.bracket_sec <= 0:
            raise ValueError("bracket_sec must be positive")
        if self.min_cluster_gap_sec <= 0:
            raise ValueError("min_cluster_gap_sec must be positive")
        if self.person_conf < 0 or self.person_conf > 1:
            raise ValueError("person_conf must be between 0 and 1")
        if not self.person_model:
            raise ValueError("person_model must be non-empty")
        if self.presence_gap_sec < 0:
            raise ValueError("presence_gap_sec must be non-negative")
        if self.episode_max_sec <= 0:
            raise ValueError("episode_max_sec must be positive")
        if self.trigger_zone_margin < 0:
            raise ValueError("trigger_zone_margin must be non-negative")
        if self.episode_pad_sec < 0:
            raise ValueError("episode_pad_sec must be non-negative")


@dataclass(frozen=True)
class TripwireCandidate:
    center_sec: float
    start_sec: float
    end_sec: float
    trigger_mode: TriggerMode
    peak_tile_score: float
    flash_ratio: float
    source: str | None = None
    candidate_id: str | None = None
    episode_split_index: int | None = None
    episode_split_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["center_sec"] = round(self.center_sec, 3)
        row["start_sec"] = round(self.start_sec, 3)
        row["end_sec"] = round(self.end_sec, 3)
        row["peak_tile_score"] = round(self.peak_tile_score, 6)
        row["flash_ratio"] = _round_flash_ratio(self.flash_ratio)
        return row


@dataclass(frozen=True)
class TripwireSample:
    timestamp_sec: float
    peak_tile_score: float
    whole_zone_motion: float
    flash_reference_motion: float
    flash_ratio: float


@dataclass(frozen=True)
class PersonDetection:
    xyxy: tuple[float, float, float, float]
    confidence: float
    class_id: int = 0


@dataclass(frozen=True)
class PersonOccupancySample:
    timestamp_sec: float
    confidence: float


@dataclass(frozen=True)
class VisitEpisode:
    start_sec: float
    end_sec: float
    peak_confidence: float


@dataclass(frozen=True)
class PersonDetectorLoadResult:
    detector: Any | None
    status: str
    requested_model: str
    loaded_model: str | None
    message: str


class ZoneCropper:
    def __init__(self, *, frame_shape: tuple[int, int, int], polygon: list[list[float]]) -> None:
        self.frame_height = int(frame_shape[0])
        self.frame_width = int(frame_shape[1])
        self.points = polygon_to_pixels(polygon, width=self.frame_width, height=self.frame_height)
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("zone tripwire requires cv2; use the repo .venv") from exc
        mask = np.zeros((self.frame_height, self.frame_width), dtype=np.uint8)
        cv2.fillPoly(mask, [self.points.astype(np.int32)], 255)
        x, y, w, h = cv2.boundingRect(self.points.astype(np.int32))
        if w <= 0 or h <= 0:
            raise ValueError("output zone polygon produced an empty crop")
        self.mask = mask
        self.bounds = (int(x), int(y), int(w), int(h))
        self.crop_mask = mask[y : y + h, x : x + w]

    def crop(self, frame: np.ndarray) -> np.ndarray:
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("zone tripwire requires cv2; use the repo .venv") from exc
        masked = cv2.bitwise_and(frame, frame, mask=self.mask)
        x, y, w, h = self.bounds
        return masked[y : y + h, x : x + w]


class UltralyticsPersonDetector:
    def __init__(self, model: Any, *, model_name: str, conf: float) -> None:
        self.model = model
        self.model_name = model_name
        self.conf = conf

    def detect(self, frame: np.ndarray) -> list[PersonDetection]:
        results = self.model.predict(frame, verbose=False, conf=self.conf, classes=[0])
        detections: list[PersonDetection] = []
        for result in results or []:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            xyxy_values = _as_list(getattr(boxes, "xyxy", []))
            conf_values = _as_list(getattr(boxes, "conf", []))
            cls_values = _as_list(getattr(boxes, "cls", []))
            for index, xyxy in enumerate(xyxy_values):
                if len(xyxy) != 4:
                    continue
                confidence = float(conf_values[index]) if index < len(conf_values) else 0.0
                class_id = int(cls_values[index]) if index < len(cls_values) else 0
                detections.append(
                    PersonDetection(
                        xyxy=(float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
                        confidence=confidence,
                        class_id=class_id,
                    )
                )
        return detections


def load_person_detector(config: TripwireConfig) -> PersonDetectorLoadResult:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        message = f"person_presence skipped: ultralytics unavailable ({exc})"
        LOGGER.warning(message)
        return PersonDetectorLoadResult(
            detector=None,
            status="skipped",
            requested_model=config.person_model,
            loaded_model=None,
            message=message,
        )

    candidates = [config.person_model]
    if config.person_model != "yolov8n.pt":
        candidates.append("yolov8n.pt")
    errors: list[str] = []
    for model_name in candidates:
        try:
            model = YOLO(model_name)
            status = "loaded" if model_name == config.person_model else "fallback_loaded"
            message = (
                f"person_presence loaded {model_name}"
                if status == "loaded"
                else f"person_presence fell back to {model_name}; requested {config.person_model}"
            )
            if status == "fallback_loaded":
                LOGGER.warning(message)
            else:
                LOGGER.info(message)
            return PersonDetectorLoadResult(
                detector=UltralyticsPersonDetector(model, model_name=model_name, conf=config.person_conf),
                status=status,
                requested_model=config.person_model,
                loaded_model=model_name,
                message=message,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{model_name}: {exc}")
            if model_name == config.person_model and config.person_model != "yolov8n.pt":
                LOGGER.warning("person_presence model %s unavailable (%s); trying yolov8n.pt", model_name, exc)

    message = "person_presence skipped: no usable person model (" + "; ".join(errors) + ")"
    LOGGER.warning(message)
    return PersonDetectorLoadResult(
        detector=None,
        status="skipped",
        requested_model=config.person_model,
        loaded_model=None,
        message=message,
    )


def run_tripwire_on_video(
    *,
    video_path: Path,
    output_zone_polygon: list[list[float]],
    config: TripwireConfig | None = None,
    source_label: str | None = None,
    person_detector: Any | None = None,
    person_detector_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or TripwireConfig()
    config.validate()
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("zone tripwire requires cv2; use the repo .venv") from exc
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")

    detector = person_detector
    detector_status = person_detector_status
    if config.trigger == "person_presence":
        if detector is not None:
            detector_status = detector_status or {
                "status": "loaded",
                "requested_model": config.person_model,
                "loaded_model": getattr(detector, "model_name", "injected"),
                "message": "person_presence using injected detector",
            }
        elif detector_status is None:
            loaded = load_person_detector(config)
            detector = loaded.detector
            detector_status = {
                "status": loaded.status,
                "requested_model": loaded.requested_model,
                "loaded_model": loaded.loaded_model,
                "message": loaded.message,
            }
    else:
        detector_status = {
            "status": "not_requested",
            "requested_model": config.person_model,
            "loaded_model": None,
            "message": "person_presence not requested",
        }

    samples: list[TripwireSample] = []
    burst_samples: list[TripwireSample] = []
    quiet_candidates: list[TripwireCandidate] = []
    occupied_samples: list[PersonOccupancySample] = []
    dropped_flash = 0
    frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    duration_sec = frame_count / source_fps if frame_count > 0 and source_fps > 0 else 0.0

    previous_zone: np.ndarray | None = None
    previous_calm_zone: np.ndarray | None = None
    previous_calm_sec: float | None = None
    last_state_probe_sec = -math.inf
    cropper: ZoneCropper | None = None
    trigger_bbox: tuple[float, float, float, float] | None = None

    try:
        for timestamp_sec, frame in iter_sampled_frames(
            capture,
            source_fps=source_fps,
            sample_fps=config.sample_fps,
        ):
            if cropper is None:
                cropper = ZoneCropper(frame_shape=frame.shape, polygon=output_zone_polygon)
                trigger_bbox = expand_zone(
                    output_zone_polygon,
                    margin=config.trigger_zone_margin,
                    frame_w=int(frame.shape[1]),
                    frame_h=int(frame.shape[0]),
                )
            if config.trigger == "person_presence" and detector is not None and trigger_bbox is not None:
                occupancy = person_occupancy_for_frame(
                    frame,
                    detector=detector,
                    trigger_bbox=trigger_bbox,
                    person_conf=config.person_conf,
                )
                if occupancy is not None:
                    occupied_samples.append(
                        PersonOccupancySample(timestamp_sec=timestamp_sec, confidence=occupancy.confidence)
                    )
            zone = cropper.crop(frame)
            zone_gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
            if previous_zone is None:
                previous_zone = zone_gray
                continue

            peak_score = tiled_change_score(
                previous_zone,
                zone_gray,
                grid_size=config.grid_size,
                method=config.score_method,
            )
            whole_zone_motion = whole_zone_absdiff(previous_zone, zone_gray, mask=cropper.crop_mask)
            flash_ratio = zone_uniformity_flash_ratio(
                zone_local_change=peak_score,
                zone_mean_change=whole_zone_motion,
            )
            sample = TripwireSample(
                timestamp_sec=timestamp_sec,
                peak_tile_score=peak_score,
                whole_zone_motion=whole_zone_motion,
                flash_reference_motion=whole_zone_motion,
                flash_ratio=flash_ratio,
            )
            samples.append(sample)

            if peak_score >= config.burst_threshold:
                if flash_ratio >= config.min_flash_ratio:
                    burst_samples.append(sample)
                else:
                    dropped_flash += 1

            if timestamp_sec - last_state_probe_sec >= config.state_interval_sec:
                last_state_probe_sec = timestamp_sec
                if whole_zone_motion <= config.calm_threshold:
                    if previous_calm_zone is not None and previous_calm_sec is not None:
                        state_score = tiled_change_score(
                            previous_calm_zone,
                            zone_gray,
                            grid_size=config.grid_size,
                            method=config.score_method,
                        )
                        state_zone_motion = whole_zone_absdiff(previous_calm_zone, zone_gray, mask=cropper.crop_mask)
                        state_flash_ratio = zone_uniformity_flash_ratio(
                            zone_local_change=state_score,
                            zone_mean_change=state_zone_motion,
                        )
                        if state_score >= config.state_threshold:
                            if state_flash_ratio >= config.min_flash_ratio:
                                center_sec = (previous_calm_sec + timestamp_sec) / 2.0
                                quiet_candidates.append(
                                    build_candidate(
                                        center_sec=center_sec,
                                        duration_sec=duration_sec,
                                        trigger_mode="quiet_state_diff",
                                        peak_tile_score=state_score,
                                        flash_ratio=state_flash_ratio,
                                        bracket_sec=config.bracket_sec,
                                        source=source_label or str(video_path),
                                    )
                                )
                            else:
                                dropped_flash += 1
                    previous_calm_zone = zone_gray.copy()
                    previous_calm_sec = timestamp_sec

            previous_zone = zone_gray
    finally:
        capture.release()

    burst_candidates = burst_candidates_from_samples(
        burst_samples,
        duration_sec=duration_sec,
        bracket_sec=config.bracket_sec,
        min_cluster_gap_sec=config.min_cluster_gap_sec,
        source=source_label or str(video_path),
    )
    raw_pixel_candidate_count = len(burst_candidates) + len(quiet_candidates)
    person_episodes: list[VisitEpisode] = []
    person_candidates: list[TripwireCandidate] = []
    backstop_dropped_in_episode = 0
    if config.trigger == "person_presence" and detector is not None:
        person_episodes = build_visit_episodes(occupied_samples, presence_gap_sec=config.presence_gap_sec)
        person_candidates = visit_candidates_from_episodes(
            person_episodes,
            duration_sec=duration_sec,
            episode_max_sec=config.episode_max_sec,
            episode_pad_sec=config.episode_pad_sec,
            source=source_label or str(video_path),
        )
        candidates, backstop_dropped_in_episode = merge_person_visits_with_backstop(
            person_candidates,
            quiet_candidates,
        )
        if config.include_motion_burst:
            candidates.extend(burst_candidates)
    elif config.trigger == "person_presence":
        candidates = list(quiet_candidates)
        if config.include_motion_burst:
            candidates.extend(burst_candidates)
    else:
        candidates = list(quiet_candidates) + list(burst_candidates)
    candidates = sorted(candidates, key=lambda row: (row.center_sec, row.trigger_mode))
    rows = []
    for index, candidate in enumerate(candidates, start=1):
        row = candidate.to_dict()
        row["candidate_id"] = candidate.candidate_id or f"tripwire-{index:05d}"
        rows.append(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "source": source_label or str(video_path),
        "config": asdict(config),
        "summary": {
            "candidate_count": len(rows),
            "motion_burst_count": len([row for row in rows if row["trigger_mode"] == "motion_burst"]),
            "quiet_state_diff_count": len([row for row in rows if row["trigger_mode"] == "quiet_state_diff"]),
            "person_visit_count": len([row for row in rows if row["trigger_mode"] == "person_visit"]),
            "raw_pixel_candidate_count": raw_pixel_candidate_count,
            "candidate_count_before_dedup": raw_pixel_candidate_count,
            "candidate_count_after_dedup": len(rows),
            "person_occupied_frame_count": len(occupied_samples),
            "person_visit_episode_count": len(person_episodes),
            "backstop_dropped_in_episode_count": backstop_dropped_in_episode,
            "sample_count": len(samples),
            "dropped_flash_count": dropped_flash,
            "duration_sec": round(duration_sec, 3),
            "person_detector": detector_status,
        },
        "candidates": rows,
    }


def run_tripwire_on_segment_manifest(
    *,
    segment_manifest_path: Path,
    output_zone_polygon: list[list[float]],
    config: TripwireConfig | None = None,
    person_detector: Any | None = None,
) -> dict[str, Any]:
    config = config or TripwireConfig()
    config.validate()
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    validate_segment_manifest(manifest)
    all_candidates: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    detector = person_detector
    detector_status: dict[str, Any] | None = None
    if config.trigger == "person_presence":
        if detector is None:
            loaded = load_person_detector(config)
            detector = loaded.detector
            detector_status = {
                "status": loaded.status,
                "requested_model": loaded.requested_model,
                "loaded_model": loaded.loaded_model,
                "message": loaded.message,
            }
        else:
            detector_status = {
                "status": "loaded",
                "requested_model": config.person_model,
                "loaded_model": getattr(detector, "model_name", "injected"),
                "message": "person_presence using injected detector",
            }
    for segment in manifest.get("segments") or []:
        if not segment.get("decode_ok", True):
            continue
        segment_path = _resolve_segment_path(segment_manifest_path, segment)
        payload = run_tripwire_on_video(
            video_path=segment_path,
            output_zone_polygon=output_zone_polygon,
            config=config,
            source_label=str(segment_path),
            person_detector=detector,
            person_detector_status=detector_status,
        )
        for candidate in payload["candidates"]:
            row = dict(candidate)
            row["segment_id"] = segment.get("segment_id")
            row["segment_path"] = str(segment_path)
            row["segment_start_wall_ts"] = segment.get("start_wall_ts")
            row["segment_end_wall_ts"] = segment.get("end_wall_ts")
            row["center_offset_sec"] = row["center_sec"]
            row["start_offset_sec"] = row["start_sec"]
            row["end_offset_sec"] = row["end_sec"]
            all_candidates.append(row)
        summaries.append({"segment_id": segment.get("segment_id"), **payload["summary"]})
    for index, row in enumerate(all_candidates, start=1):
        row["candidate_id"] = f"tripwire-{index:05d}"
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(segment_manifest_path),
        "station_id": manifest.get("station_id"),
        "config": asdict(config),
        "summary": {
            "candidate_count": len(all_candidates),
            "motion_burst_count": len([row for row in all_candidates if row["trigger_mode"] == "motion_burst"]),
            "quiet_state_diff_count": len([row for row in all_candidates if row["trigger_mode"] == "quiet_state_diff"]),
            "person_visit_count": len([row for row in all_candidates if row["trigger_mode"] == "person_visit"]),
            "raw_pixel_candidate_count": sum(int(row.get("raw_pixel_candidate_count", 0)) for row in summaries),
            "candidate_count_before_dedup": sum(int(row.get("candidate_count_before_dedup", 0)) for row in summaries),
            "candidate_count_after_dedup": len(all_candidates),
            "person_occupied_frame_count": sum(int(row.get("person_occupied_frame_count", 0)) for row in summaries),
            "person_visit_episode_count": sum(int(row.get("person_visit_episode_count", 0)) for row in summaries),
            "backstop_dropped_in_episode_count": sum(int(row.get("backstop_dropped_in_episode_count", 0)) for row in summaries),
            "person_detector": detector_status
            or {
                "status": "not_requested",
                "requested_model": config.person_model,
                "loaded_model": None,
                "message": "person_presence not requested",
            },
            "segment_count": len(manifest.get("segments") or []),
            "processed_segment_count": len(summaries),
            "segments": summaries,
        },
        "candidates": all_candidates,
    }


def build_candidate(
    *,
    center_sec: float,
    duration_sec: float,
    trigger_mode: TriggerMode,
    peak_tile_score: float,
    flash_ratio: float,
    bracket_sec: float,
    source: str | None = None,
) -> TripwireCandidate:
    return TripwireCandidate(
        center_sec=center_sec,
        start_sec=max(0.0, center_sec - bracket_sec),
        end_sec=min(duration_sec, center_sec + bracket_sec) if duration_sec > 0 else center_sec + bracket_sec,
        trigger_mode=trigger_mode,
        peak_tile_score=peak_tile_score,
        flash_ratio=flash_ratio,
        source=source,
    )


def build_visit_candidate(
    *,
    start_sec: float,
    end_sec: float,
    duration_sec: float,
    peak_confidence: float,
    episode_pad_sec: float,
    source: str | None = None,
    episode_split_index: int | None = None,
    episode_split_count: int | None = None,
) -> TripwireCandidate:
    center_sec = (start_sec + end_sec) / 2.0
    return TripwireCandidate(
        center_sec=center_sec,
        start_sec=max(0.0, start_sec - episode_pad_sec),
        end_sec=min(duration_sec, end_sec + episode_pad_sec) if duration_sec > 0 else end_sec + episode_pad_sec,
        trigger_mode="person_visit",
        peak_tile_score=peak_confidence,
        flash_ratio=math.inf,
        source=source,
        episode_split_index=episode_split_index,
        episode_split_count=episode_split_count,
    )


def expand_zone(
    polygon: list[list[float]],
    *,
    margin: float,
    frame_w: int,
    frame_h: int,
) -> tuple[float, float, float, float]:
    if margin < 0:
        raise ValueError("margin must be non-negative")
    points = polygon_to_pixels(polygon, width=frame_w, height=frame_h).astype(float)
    min_x = float(np.min(points[:, 0]))
    max_x = float(np.max(points[:, 0]))
    min_y = float(np.min(points[:, 1]))
    max_y = float(np.max(points[:, 1]))
    width = max(0.0, max_x - min_x)
    height = max(0.0, max_y - min_y)
    pad_x = width * margin
    pad_y = height * margin
    return (
        max(0.0, min_x - pad_x),
        max(0.0, min_y - pad_y),
        min(float(frame_w), max_x + pad_x),
        min(float(frame_h), max_y + pad_y),
    )


def person_occupancy_for_frame(
    frame: np.ndarray,
    *,
    detector: Any,
    trigger_bbox: tuple[float, float, float, float],
    person_conf: float,
) -> PersonDetection | None:
    best: PersonDetection | None = None
    for raw in detector.detect(frame):
        detection = coerce_person_detection(raw)
        if detection.class_id != 0 or detection.confidence < person_conf:
            continue
        if not box_touches_trigger_zone(detection.xyxy, trigger_bbox):
            continue
        if best is None or detection.confidence > best.confidence:
            best = detection
    return best


def coerce_person_detection(raw: Any) -> PersonDetection:
    if isinstance(raw, PersonDetection):
        return raw
    if isinstance(raw, dict):
        xyxy = raw.get("xyxy") or raw.get("box") or raw.get("bbox")
        if xyxy is None:
            raise ValueError("person detection dict must include xyxy, box, or bbox")
        confidence = raw.get("confidence", raw.get("conf", 0.0))
        class_id = raw.get("class_id", raw.get("cls", 0))
        return PersonDetection(
            xyxy=(float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
            confidence=float(confidence),
            class_id=int(class_id),
        )
    xyxy = getattr(raw, "xyxy")
    return PersonDetection(
        xyxy=(float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
        confidence=float(getattr(raw, "confidence", getattr(raw, "conf", 0.0))),
        class_id=int(getattr(raw, "class_id", getattr(raw, "cls", 0))),
    )


def box_touches_trigger_zone(
    xyxy: tuple[float, float, float, float],
    trigger_bbox: tuple[float, float, float, float],
) -> bool:
    x1, y1, x2, y2 = xyxy
    tx1, ty1, tx2, ty2 = trigger_bbox
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    if tx1 <= center_x <= tx2 and ty1 <= center_y <= ty2:
        return True
    return bbox_iou(xyxy, trigger_bbox) > 0.0


def bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def build_visit_episodes(
    occupied_samples: list[PersonOccupancySample],
    *,
    presence_gap_sec: float,
) -> list[VisitEpisode]:
    if presence_gap_sec < 0:
        raise ValueError("presence_gap_sec must be non-negative")
    if not occupied_samples:
        return []
    ordered = sorted(occupied_samples, key=lambda sample: sample.timestamp_sec)
    episodes: list[VisitEpisode] = []
    start_sec = ordered[0].timestamp_sec
    last_sec = ordered[0].timestamp_sec
    peak_confidence = ordered[0].confidence
    for sample in ordered[1:]:
        if sample.timestamp_sec - last_sec > presence_gap_sec:
            episodes.append(VisitEpisode(start_sec=start_sec, end_sec=last_sec, peak_confidence=peak_confidence))
            start_sec = sample.timestamp_sec
            peak_confidence = sample.confidence
        else:
            peak_confidence = max(peak_confidence, sample.confidence)
        last_sec = sample.timestamp_sec
    episodes.append(VisitEpisode(start_sec=start_sec, end_sec=last_sec, peak_confidence=peak_confidence))
    return episodes


def visit_candidates_from_episodes(
    episodes: list[VisitEpisode],
    *,
    duration_sec: float,
    episode_max_sec: float,
    episode_pad_sec: float,
    source: str | None,
) -> list[TripwireCandidate]:
    candidates: list[TripwireCandidate] = []
    for episode in episodes:
        parts = split_visit_episode(episode, episode_max_sec=episode_max_sec)
        split_count = len(parts)
        for index, part in enumerate(parts, start=1):
            candidates.append(
                build_visit_candidate(
                    start_sec=part.start_sec,
                    end_sec=part.end_sec,
                    duration_sec=duration_sec,
                    peak_confidence=part.peak_confidence,
                    episode_pad_sec=episode_pad_sec,
                    source=source,
                    episode_split_index=index if split_count > 1 else None,
                    episode_split_count=split_count if split_count > 1 else None,
                )
            )
    return candidates


def split_visit_episode(episode: VisitEpisode, *, episode_max_sec: float) -> list[VisitEpisode]:
    if episode_max_sec <= 0:
        raise ValueError("episode_max_sec must be positive")
    if episode.end_sec - episode.start_sec <= episode_max_sec:
        return [episode]
    parts: list[VisitEpisode] = []
    current_start = episode.start_sec
    while current_start < episode.end_sec:
        current_end = min(episode.end_sec, current_start + episode_max_sec)
        parts.append(
            VisitEpisode(
                start_sec=current_start,
                end_sec=current_end,
                peak_confidence=episode.peak_confidence,
            )
        )
        current_start = current_end
    return parts


def merge_person_visits_with_backstop(
    person_candidates: list[TripwireCandidate],
    quiet_candidates: list[TripwireCandidate],
) -> tuple[list[TripwireCandidate], int]:
    merged = list(person_candidates)
    dropped = 0
    for candidate in quiet_candidates:
        if any(person.start_sec <= candidate.center_sec <= person.end_sec for person in person_candidates):
            dropped += 1
            continue
        merged.append(candidate)
    return merged, dropped


def burst_candidates_from_samples(
    samples: list[TripwireSample],
    *,
    duration_sec: float,
    bracket_sec: float,
    min_cluster_gap_sec: float,
    source: str | None,
) -> list[TripwireCandidate]:
    candidates: list[TripwireCandidate] = []
    for cluster in cluster_samples(samples, min_cluster_gap_sec=min_cluster_gap_sec):
        peak = max(cluster, key=lambda sample: sample.peak_tile_score)
        candidates.append(
            build_candidate(
                center_sec=peak.timestamp_sec,
                duration_sec=duration_sec,
                trigger_mode="motion_burst",
                peak_tile_score=peak.peak_tile_score,
                flash_ratio=peak.flash_ratio,
                bracket_sec=bracket_sec,
                source=source,
            )
        )
    return candidates


def cluster_samples(samples: list[TripwireSample], *, min_cluster_gap_sec: float) -> list[list[TripwireSample]]:
    if not samples:
        return []
    ordered = sorted(samples, key=lambda sample: sample.timestamp_sec)
    clusters: list[list[TripwireSample]] = []
    current = [ordered[0]]
    for sample in ordered[1:]:
        if sample.timestamp_sec - current[-1].timestamp_sec > min_cluster_gap_sec:
            clusters.append(current)
            current = []
        current.append(sample)
    clusters.append(current)
    return clusters


def tiled_change_score(
    before_gray: np.ndarray,
    after_gray: np.ndarray,
    *,
    grid_size: int = DEFAULT_GRID_SIZE,
    method: ScoreMethod = "tiled_absdiff",
) -> float:
    if before_gray.shape != after_gray.shape:
        raise ValueError("before_gray and after_gray must have the same shape")
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    if method == "tiled_absdiff":
        score_image = np.abs(after_gray.astype(np.float32) - before_gray.astype(np.float32)) / 255.0
        return max_tile_mean(score_image, grid_size=grid_size)
    if method == "tiled_edge":
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("tiled_edge requires cv2; use the repo .venv") from exc
        before_edge = cv2.Sobel(before_gray, cv2.CV_32F, 1, 1, ksize=3)
        after_edge = cv2.Sobel(after_gray, cv2.CV_32F, 1, 1, ksize=3)
        score_image = np.clip(np.abs(after_edge - before_edge) / 255.0, 0.0, 1.0)
        return max_tile_mean(score_image, grid_size=grid_size)
    if method == "tiled_ssim":
        return max_tile_ssim_drop(before_gray, after_gray, grid_size=grid_size)
    raise ValueError(f"unsupported score method: {method}")


def whole_zone_absdiff(before_gray: np.ndarray, after_gray: np.ndarray, *, mask: np.ndarray | None = None) -> float:
    if before_gray.shape != after_gray.shape:
        raise ValueError("before_gray and after_gray must have the same shape")
    diff = np.abs(after_gray.astype(np.float32) - before_gray.astype(np.float32)) / 255.0
    if mask is not None:
        if mask.shape != before_gray.shape:
            raise ValueError("mask must have the same shape as before_gray and after_gray")
        selected = diff[mask > 0]
        if selected.size == 0:
            return 0.0
        return float(selected.mean())
    return float(diff.mean())


def max_tile_mean(score_image: np.ndarray, *, grid_size: int) -> float:
    height, width = score_image.shape[:2]
    max_score = 0.0
    for y0, y1, x0, x1 in tile_bounds(height=height, width=width, grid_size=grid_size):
        tile = score_image[y0:y1, x0:x1]
        if tile.size:
            max_score = max(max_score, float(tile.mean()))
    return max_score


def max_tile_ssim_drop(before_gray: np.ndarray, after_gray: np.ndarray, *, grid_size: int) -> float:
    height, width = before_gray.shape[:2]
    max_drop = 0.0
    for y0, y1, x0, x1 in tile_bounds(height=height, width=width, grid_size=grid_size):
        before_tile = before_gray[y0:y1, x0:x1].astype(np.float32) / 255.0
        after_tile = after_gray[y0:y1, x0:x1].astype(np.float32) / 255.0
        if before_tile.size:
            max_drop = max(max_drop, 1.0 - simple_ssim(before_tile, after_tile))
    return float(np.clip(max_drop, 0.0, 1.0))


def simple_ssim(a: np.ndarray, b: np.ndarray) -> float:
    c1 = 0.01**2
    c2 = 0.03**2
    mean_a = float(a.mean())
    mean_b = float(b.mean())
    var_a = float(a.var())
    var_b = float(b.var())
    cov = float(((a - mean_a) * (b - mean_b)).mean())
    numerator = (2 * mean_a * mean_b + c1) * (2 * cov + c2)
    denominator = (mean_a**2 + mean_b**2 + c1) * (var_a + var_b + c2)
    if denominator == 0:
        return 1.0
    return float(np.clip(numerator / denominator, -1.0, 1.0))


def tile_bounds(*, height: int, width: int, grid_size: int) -> list[tuple[int, int, int, int]]:
    rows: list[tuple[int, int, int, int]] = []
    for row in range(grid_size):
        y0 = int(round(row * height / grid_size))
        y1 = int(round((row + 1) * height / grid_size))
        for col in range(grid_size):
            x0 = int(round(col * width / grid_size))
            x1 = int(round((col + 1) * width / grid_size))
            rows.append((y0, max(y1, y0 + 1), x0, max(x1, x0 + 1)))
    return rows


def zone_uniformity_flash_ratio(*, zone_local_change: float, zone_mean_change: float) -> float:
    """High means local placement-like change; near 1 means uniform zone flash."""
    if zone_mean_change <= 1e-9:
        return math.inf if zone_local_change > 0 else 0.0
    return float(zone_local_change / zone_mean_change)


def iter_sampled_frames(capture: Any, *, source_fps: float, sample_fps: float) -> Any:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    sample_stride = max(1.0, source_fps / sample_fps) if source_fps > 0 else 1.0
    next_sample_index = 0.0
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        target_index = int(round(next_sample_index))
        if frame_index >= target_index:
            timestamp_sec = frame_index / source_fps if source_fps > 0 else float(frame_index) / sample_fps
            yield round(timestamp_sec, 6), frame
            while int(round(next_sample_index)) <= frame_index:
                next_sample_index += sample_stride
        frame_index += 1


def sample_timestamps(*, duration_sec: float, sample_fps: float) -> list[float]:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if duration_sec <= 0:
        return [0.0]
    step = 1.0 / sample_fps
    timestamps: list[float] = []
    current = 0.0
    while current <= duration_sec:
        timestamps.append(round(current, 6))
        current += step
    return timestamps


def polygon_to_pixels(polygon: list[list[float]], *, width: int, height: int) -> np.ndarray:
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least three points")
    points = []
    normalized = all(0.0 <= float(coord) <= 1.0 for point in polygon for coord in point)
    for point in polygon:
        if len(point) != 2:
            raise ValueError("polygon points must be [x, y]")
        x = float(point[0])
        y = float(point[1])
        if normalized:
            x *= width
            y *= height
        points.append([round(x), round(y)])
    return np.array(points, dtype=np.int32)


def load_output_zone_polygon(station_calibration_path: Path) -> list[list[float]]:
    payload = json.loads(station_calibration_path.read_text(encoding="utf-8"))
    polygons = payload.get("output_polygons") or []
    if not polygons:
        raise ValueError("station calibration must include output_polygons")
    return polygons[0]


def write_tripwire_payload(path: Path, payload: dict[str, Any], *, force: bool = True) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _as_list(value: Any) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def _round_flash_ratio(value: float) -> float | str:
    if math.isinf(value):
        return "inf"
    return round(value, 6)
