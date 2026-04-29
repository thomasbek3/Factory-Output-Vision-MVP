from __future__ import annotations

import os
from pathlib import Path


def get_db_path() -> Path:
    raw = os.getenv("FC_DB_PATH", "./data/factory_counter.db")
    return Path(raw).expanduser().resolve()


def is_demo_mode() -> bool:
    return os.getenv("FC_DEMO_MODE", "0") == "1"


def get_demo_video_path() -> Path:
    raw = os.getenv("FC_DEMO_VIDEO_PATH", "")
    return Path(raw).expanduser().resolve() if raw else Path()


def get_runtime_calibration_path() -> Path | None:
    raw = os.getenv("FC_RUNTIME_CALIBRATION_PATH", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def get_demo_video_library_dir() -> Path:
    raw = os.getenv("FC_DEMO_VIDEO_LIBRARY_DIR", "./data/demo_videos")
    return Path(raw).expanduser().resolve()


def get_demo_playback_speed() -> float:
    return float(os.getenv("FC_DEMO_PLAYBACK_SPEED", "1.0"))


def is_demo_loop_enabled() -> bool:
    explicit = os.getenv("FC_DEMO_LOOP")
    if explicit is not None:
        return explicit == "1"
    return not (get_counting_mode() == "event_based" and get_runtime_calibration_path() is not None)


def get_demo_count_mode() -> str:
    explicit = os.getenv("FC_DEMO_COUNT_MODE", "").strip()
    if explicit:
        return explicit
    if get_counting_mode() == "event_based" and get_runtime_calibration_path() is not None:
        return "deterministic_file_runner"
    return "live_reader_snapshot"


def get_demo_count_cache_path() -> Path | None:
    raw = os.getenv("FC_DEMO_COUNT_CACHE_PATH", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def get_log_dir() -> Path:
    raw = os.getenv("FC_LOG_DIR", "./data/logs")
    return Path(raw).expanduser().resolve()


def get_frontend_dist_path() -> Path:
    raw = os.getenv("FC_FRONTEND_DIST", "./frontend/dist")
    return Path(raw).expanduser().resolve()


def get_health_sample_interval_sec() -> float:
    return float(os.getenv("FC_HEALTH_SAMPLE_INTERVAL_SEC", "10"))


def get_frame_stall_timeout_sec() -> float:
    return float(os.getenv("FC_FRAME_STALL_TIMEOUT_SEC", "3.0"))


def get_reconnect_backoff_initial_sec() -> float:
    return float(os.getenv("FC_RECONNECT_BACKOFF_INITIAL_SEC", "1.0"))


def get_reconnect_backoff_max_sec() -> float:
    return float(os.getenv("FC_RECONNECT_BACKOFF_MAX_SEC", "8.0"))


def get_processing_fps() -> float:
    return float(os.getenv("FC_PROCESSING_FPS", "10"))


def get_reader_fps() -> float:
    return float(os.getenv("FC_READER_FPS", "12"))


def get_min_contour_area() -> float:
    return float(os.getenv("FC_MIN_CONTOUR_AREA", "150"))


def get_max_contour_area() -> float:
    return float(os.getenv("FC_MAX_CONTOUR_AREA", "50000"))


def get_tracker_max_age_frames() -> int:
    """How many frames a track survives without detection before deletion.
    Increased from 5 to 15 for zone-based counting where objects may be
    momentarily occluded or YOLO confidence fluctuates."""
    return int(os.getenv("FC_TRACK_MAX_AGE_FRAMES", "15"))


def get_tracker_max_match_distance() -> float:
    """Max pixel distance to match a detection to an existing track.
    Increased from 60 to 100 for zone-based counting with less predictable
    object motion patterns."""
    return float(os.getenv("FC_TRACK_MAX_MATCH_DISTANCE", "100"))


def get_count_line_deadband_px() -> float:
    return float(os.getenv("FC_COUNT_LINE_DEADBAND_PX", "18"))


def get_count_track_min_frames() -> int:
    return int(os.getenv("FC_COUNT_TRACK_MIN_FRAMES", "3"))


def get_count_track_min_travel_px() -> float:
    return float(os.getenv("FC_COUNT_TRACK_MIN_TRAVEL_PX", "28"))


def get_stop_minutes() -> int:
    return int(os.getenv("FC_STOP_MINUTES", "2"))


def get_drop_minutes() -> int:
    return int(os.getenv("FC_DROP_MINUTES", "3"))


def get_drop_threshold() -> float:
    return float(os.getenv("FC_DROP_THRESHOLD", "0.60"))


def get_calibration_minutes() -> int:
    return int(os.getenv("FC_CALIBRATION_MINUTES", "5"))


def is_person_detect_enabled() -> bool:
    return os.getenv("FC_PERSON_DETECT_ENABLED", "0") == "1"


def get_person_detect_fps() -> float:
    return float(os.getenv("FC_PERSON_DETECT_FPS", "1"))


def get_operator_absent_minutes() -> int:
    return int(os.getenv("FC_OPERATOR_ABSENT_MINUTES", "2"))


def get_person_conf_threshold() -> float:
    return float(os.getenv("FC_PERSON_CONF_THRESHOLD", "0.5"))


def is_person_ignore_enabled() -> bool:
    return os.getenv("FC_PERSON_IGNORE_ENABLED", "1") == "1"


def get_person_ignore_fps() -> float:
    return float(os.getenv("FC_PERSON_IGNORE_FPS", "1"))


def get_yolo_conf_threshold() -> float:
    explicit = os.getenv("FC_YOLO_CONF_THRESHOLD")
    if explicit is not None:
        return float(explicit)
    if get_counting_mode() == "event_based" and get_runtime_calibration_path() is not None:
        return 0.15
    if get_counting_mode() == "event_based":
        return 0.40
    return 0.3


def get_yolo_model_path() -> str:
    explicit = os.getenv("FC_YOLO_MODEL_PATH")
    if explicit is not None:
        return explicit
    if get_counting_mode() == "event_based":
        return "models/panel_in_transit.pt"
    return "yolov8n.pt"


def get_yolo_person_class_id() -> int:
    return int(os.getenv("FC_YOLO_PERSON_CLASS_ID", "0"))


def get_yolo_excluded_classes() -> list[int]:
    """Classes to exclude from object counting (default: 0=person)."""
    explicit = os.getenv("FC_YOLO_EXCLUDED_CLASSES")
    if explicit is not None:
        if not explicit.strip():
            return []
        return [int(c.strip()) for c in explicit.split(",") if c.strip().isdigit()]
    if get_counting_mode() == "event_based":
        return []  # Custom transit model has no person class
    return [0]


# --- YOLO zone-based counting settings ---

def get_count_min_track_frames() -> int:
    """Minimum frames a track must be seen before counting it as a new object.
    Higher = more confident (fewer false counts), lower = faster response."""
    return int(os.getenv("FC_COUNT_MIN_TRACK_FRAMES", "5"))


def get_count_debounce_sec() -> float:
    """Minimum seconds between counts from the same approximate location.
    Prevents double-counting from detection flicker / track ID reassignment."""
    return float(os.getenv("FC_COUNT_DEBOUNCE_SEC", "2.0"))


# --- Counting mode ---

def get_counting_mode() -> str:
    """'track_based' (default, existing) or 'event_based' (transit detection)."""
    return os.getenv("FC_COUNTING_MODE", "track_based")


def get_event_gap_seconds() -> float:
    """Detections more than this many seconds apart = separate events."""
    return float(os.getenv("FC_EVENT_GAP_SECONDS", "3.0"))


def get_event_min_duration_seconds() -> float:
    """Events shorter than this are filtered as flicker."""
    return float(os.getenv("FC_EVENT_MIN_DURATION_SECONDS", "2.0"))


# --- Event-based tracker settings (CentroidTracker params for event_based mode) ---

def get_event_track_max_age() -> int:
    """Max frames a track survives without detection in event_based mode.
    Higher than track_based (default 40 = ~4 sec at 10 FPS) because
    transit detections can be intermittent mid-carry."""
    return int(os.getenv("FC_EVENT_TRACK_MAX_AGE", "40"))


def get_event_track_min_frames() -> int:
    """Minimum frames a track must exist before its death counts as +1.
    Filters single-frame false positives (default 8 = ~0.8 sec at 10 FPS)."""
    return int(os.getenv("FC_EVENT_TRACK_MIN_FRAMES", "8"))


def get_event_track_max_match_distance() -> float:
    """Max pixel distance for centroid matching in event_based mode.
    Generous default (200) since usually only 1 panel in transit at a time."""
    return float(os.getenv("FC_EVENT_TRACK_MAX_MATCH_DISTANCE", "200"))
