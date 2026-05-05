from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2

from app.core.settings import (
    get_calibration_minutes,
    get_count_min_track_frames,
    get_demo_count_mode,
    get_counting_mode,
    get_drop_minutes,
    get_drop_threshold,
    get_event_gap_seconds,
    get_event_detection_cluster_distance,
    get_event_count_debounce_sec,
    get_event_min_duration_seconds,
    get_event_count_rule,
    get_event_track_max_age,
    get_event_track_max_match_distance,
    get_event_track_min_frames,
    get_event_track_min_travel_px,
    get_frame_stall_timeout_sec,
    get_health_sample_interval_sec,
    get_operator_absent_minutes,
    get_person_conf_threshold,
    get_person_ignore_fps,
    get_person_detect_fps,
    get_processing_fps,
    get_reconnect_backoff_initial_sec,
    get_reconnect_backoff_max_sec,
    get_runtime_calibration_path,
    get_stop_minutes,
    get_tracker_max_age_frames,
    get_tracker_max_match_distance,
    get_yolo_conf_threshold,
    get_yolo_excluded_classes,
    get_yolo_model_path,
    is_demo_mode,
    is_person_ignore_enabled,
    is_person_detect_enabled,
)
from app.db.config_repo import get_config, update_baseline_rate
from app.db.count_repo import clear_count_history, record_count_event
from app.db.event_repo import log_event
from app.db.health_repo import insert_health_sample
from app.services.calibration import Box, box_center
from app.services.counting import CentroidTracker, CounterState, EventBasedCounter, YoloObjectDetector, apply_roi_mask, count_dead_tracks, count_new_tracks, mark_all_tracks_counted, track_travel_px
from app.services.deterministic_demo_runner import DeterministicDemoRunner
from app.services.perception_gate import GateDecision
from app.services.person_detector import PersonDetector, point_in_polygon
from app.services.runtime_event_counter import RuntimeEventCounter, load_runtime_calibration

logger = logging.getLogger(__name__)


class VisionWorker:
    def __init__(self, video_runtime) -> None:
        self.video_runtime = video_runtime
        self._thread: threading.Thread | None = None
        self._person_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self.counter_state = CounterState()
        self._yolo_detector = YoloObjectDetector(
            model_path=get_yolo_model_path(),
            conf_threshold=get_yolo_conf_threshold(),
            excluded_classes=get_yolo_excluded_classes(),
        )
        self._tracker = CentroidTracker(
            max_age_frames=get_tracker_max_age_frames(),
            max_match_distance=get_tracker_max_match_distance(),
        )

        self._counting_mode = get_counting_mode()
        self._demo_count_mode = get_demo_count_mode()
        self._event_count_rule = get_event_count_rule()
        self._event_count_rule_config_error: str | None = None
        self._event_counter: EventBasedCounter | None = None  # kept for reference, no longer used
        self._event_tracker: CentroidTracker | None = None
        self._runtime_calibration_path = get_runtime_calibration_path() if self._counting_mode == "event_based" else None
        self._deterministic_demo_runner: DeterministicDemoRunner | None = None
        self._runtime_event_counter: RuntimeEventCounter | None = None
        if self._counting_mode == "event_based":
            if self._event_count_rule == "dead_track":
                self._event_tracker = CentroidTracker(
                    max_age_frames=get_event_track_max_age(),
                    max_match_distance=get_event_track_max_match_distance(),
                )
            elif self._runtime_calibration_path is not None:
                zones, gate = load_runtime_calibration(self._runtime_calibration_path)
                self._runtime_event_counter = RuntimeEventCounter(
                    zones=zones,
                    gate=gate,
                    tracker_match_distance=get_event_track_max_match_distance(),
                )
                if self._demo_count_mode == "deterministic_file_runner":
                    self._deterministic_demo_runner = DeterministicDemoRunner()
            elif self._event_count_rule == "placed_and_stayed":
                self._event_count_rule_config_error = "FC_EVENT_COUNT_RULE=placed_and_stayed requires FC_RUNTIME_CALIBRATION_PATH"
                logger.error(self._event_count_rule_config_error)
            else:
                self._event_tracker = CentroidTracker(
                    max_age_frames=get_event_track_max_age(),
                    max_match_distance=get_event_track_max_match_distance(),
                )

        persisted = get_config()

        self.state = "NOT_CONFIGURED"
        self.monitoring_enabled = False
        self.calibrating = False
        self.baseline_rate_per_min: float | None = persisted.get("baseline_rate_per_min")
        self.rolling_rate_per_min: float = 0.0
        self.last_frame_age_sec: float | None = None
        self.last_event: dict[str, Any] | None = None
        self.operator_absent_active = False
        self.reconnect_attempts_total = 0
        self.last_error_code: str | None = None
        self.last_error_message: str | None = None
        self._latest_debug_artifact: dict[str, Any] | None = None
        self._recent_count_events: deque[dict[str, Any]] = deque(maxlen=256)
        self._last_event_based_count_source_ts: float | None = None
        self._demo_eof_flush_applied = False
        self.person_ignore_enabled = is_person_ignore_enabled() and self._counting_mode != "event_based"
        self._runtime_total = 0
        self._proof_backed_total = 0
        self._runtime_inferred_only_total = 0

        self._current_minute_count = 0
        self._current_minute_key = self._minute_key_now()
        self._minute_history: deque[int] = deque(maxlen=120)
        self._calibration_samples: list[int] = []
        self._calibration_started_at_ts: float | None = None
        self._calibration_deadline_ts: float | None = None
        self._last_error_emit_key: tuple[str, str] | None = None
        self._last_error_emit_ts = 0.0
        self._last_health_sample_ts = 0.0
        self._last_loop_tick_ts = 0.0
        self._last_person_loop_tick_ts = 0.0
        self._reconnect_backoff_sec = max(0.1, get_reconnect_backoff_initial_sec())
        self._was_reconnecting = False

        self._person_detector = PersonDetector(get_person_conf_threshold()) if is_person_detect_enabled() else None
        self._operator_last_seen_ts: float | None = None
        self._operator_absent_emitted = False
        self._state_before_operator_absent: str | None = None
        self._latest_person_boxes: list[dict[str, int | float]] = []
        self._last_person_ignore_detect_ts = 0.0
        self._last_runtime_person_detect_ts = 0.0
        self._demo_live_started_at_ts: float | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="vision-worker", daemon=True)
        self._thread.start()

        if self._person_detector is not None and (self._person_thread is None or not self._person_thread.is_alive()):
            self._person_thread = threading.Thread(target=self._run_person_loop, name="person-detector", daemon=True)
            self._person_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._person_thread and self._person_thread.is_alive():
            self._person_thread.join(timeout=2.0)
        self._thread = None
        self._person_thread = None

    def get_status(self) -> dict[str, object]:
        with self._lock:
            self.counter_state.rollover_if_needed()
            self._rollover_completed_minute_if_needed()
            source_kind = self.video_runtime.current_source_kind()
            demo_active = bool(source_kind == "demo" and (self.monitoring_enabled or self.calibrating) and not self.video_runtime.is_demo_finished())
            demo_elapsed = 0.0 if self._deterministic_demo_runner is None else round(self._deterministic_demo_runner.current_elapsed_sec(), 2)
            return {
                "state": self.state,
                "count_source": "vision",
                "baseline_rate_per_min": self.baseline_rate_per_min,
                "calibration_progress_pct": self._get_calibration_progress_pct(),
                "calibration_elapsed_sec": self._get_calibration_elapsed_sec(),
                "calibration_target_duration_sec": self._get_calibration_target_duration_sec(),
                "rolling_rate_per_min": round(self.rolling_rate_per_min, 2),
                "counts_this_minute": self.counter_state.counts_this_minute,
                "counts_this_hour": self.counter_state.counts_this_hour,
                "runtime_total": self._runtime_total,
                "proof_backed_total": self._proof_backed_total,
                "runtime_inferred_only": self._runtime_inferred_only_total,
                "last_frame_age_sec": None if self.last_frame_age_sec is None else round(self.last_frame_age_sec, 2),
                "reconnect_attempts_total": self.reconnect_attempts_total,
                "operator_absent": self.operator_absent_active,
                "demo_elapsed_sec": demo_elapsed,
                "demo_playback_active": demo_active,
            }

    def get_metrics_payload(self) -> dict[str, Any]:
        with self._lock:
            payload = self.get_status()
            if self.last_event:
                payload["last_event"] = self.last_event
            return payload

    def get_debug_overlay(self) -> dict[str, Any] | None:
        with self._lock:
            if self._latest_debug_artifact is None:
                return None
            return {
                "mode": self._latest_debug_artifact["mode"],
                "updated_at_ts": self._latest_debug_artifact["updated_at_ts"],
                "detections": [dict(item) for item in self._latest_debug_artifact["detections"]],
                "tracks": [dict(item) for item in self._latest_debug_artifact["tracks"]],
                "person_boxes": [dict(item) for item in self._latest_debug_artifact.get("person_boxes", [])],
                "people_detected_count": len(self._latest_debug_artifact.get("person_boxes", [])),
            }

    def get_debug_snapshot_artifact(self) -> dict[str, Any] | None:
        with self._lock:
            if self._latest_debug_artifact is None:
                return None
            artifact = {
                "mode": self._latest_debug_artifact["mode"],
                "updated_at_ts": self._latest_debug_artifact["updated_at_ts"],
                "detections": [dict(item) for item in self._latest_debug_artifact["detections"]],
                "tracks": [dict(item) for item in self._latest_debug_artifact["tracks"]],
                "person_boxes": [dict(item) for item in self._latest_debug_artifact.get("person_boxes", [])],
                "people_detected_count": len(self._latest_debug_artifact.get("person_boxes", [])),
            }
            for frame_name in ("source_frame", "roi_frame", "mask_frame"):
                frame = self._latest_debug_artifact.get(frame_name)
                artifact[frame_name] = None if frame is None else frame.copy()
            return artifact

    def start_monitoring(self) -> dict[str, object]:
        monitoring_prepare_error: Exception | None = None
        source_is_demo = self.video_runtime.current_source_kind() == "demo"
        should_use_deterministic_demo = self._should_use_deterministic_demo_counting(source_is_demo=source_is_demo)
        if should_use_deterministic_demo:
            try:
                selection = self.video_runtime.current_source_selection()
                if self._deterministic_demo_runner is None or self._runtime_calibration_path is None:
                    raise RuntimeError("Deterministic demo runner is unavailable")
                self._deterministic_demo_runner.prepare(
                    video_path=Path(selection.source),
                    calibration_path=Path(self._runtime_calibration_path),
                    model_path=Path(get_yolo_model_path()),
                )
                self.video_runtime.restart()
            except Exception as exc:  # noqa: BLE001
                monitoring_prepare_error = exc
        elif source_is_demo:
            try:
                self.video_runtime.restart()
            except Exception as exc:  # noqa: BLE001
                monitoring_prepare_error = exc

        with self._lock:
            if not self._is_configured():
                self._transition("NOT_CONFIGURED", "Missing camera/demo source or output area")
                return self.get_status()
            if monitoring_prepare_error is not None:
                self._record_runtime_error("DEMO_COUNT_PREP_ERROR", str(monitoring_prepare_error))
                self._transition("IDLE", "Unable to prepare deterministic demo count")
                return self.get_status()
            self.monitoring_enabled = True
            self._demo_eof_flush_applied = False
            self._demo_live_started_at_ts = time.time() if source_is_demo else None
            self.video_runtime.reader.discard_pending_frames()
            if should_use_deterministic_demo and self._deterministic_demo_runner is not None:
                self._clear_count_state()
                self._deterministic_demo_runner.arm(playback_speed=self.video_runtime.current_demo_playback_speed())
            # Warmup: mark existing tracks as counted so objects already in the
            # output zone don't get counted as new output.
            if self._runtime_event_counter is not None:
                pass
            elif self._counting_mode == "event_based" and self._event_tracker is not None:
                mark_all_tracks_counted(self._event_tracker.tracks)
            else:
                mark_all_tracks_counted(self._tracker.tracks)
            target = "RUNNING_GREEN" if self.baseline_rate_per_min else "IDLE"
            self._transition(target, "Monitoring started")
            return self.get_status()

    def stop_monitoring(self) -> dict[str, object]:
        with self._lock:
            self.monitoring_enabled = False
            self._demo_live_started_at_ts = None
            self.operator_absent_active = False
            self._operator_absent_emitted = False
            if self._deterministic_demo_runner is not None:
                self._deterministic_demo_runner.disarm()
            if self._is_configured():
                self._transition("IDLE", "Monitoring stopped")
            else:
                self._transition("NOT_CONFIGURED", "Monitoring stopped")
            return self.get_status()

    def start_calibration(self) -> dict[str, object]:
        with self._lock:
            if not self._is_configured():
                self._transition("NOT_CONFIGURED", "Cannot calibrate: setup incomplete")
                return self.get_status()
            if self.baseline_rate_per_min is not None:
                return self.get_status()
            self.monitoring_enabled = True
            self.calibrating = True
            self._calibration_samples = []
            # Warmup: mark existing tracks as counted so pre-existing objects
            # in the output zone don't inflate the calibration baseline.
            if self._runtime_event_counter is not None:
                pass
            elif self._counting_mode == "event_based" and self._event_tracker is not None:
                mark_all_tracks_counted(self._event_tracker.tracks)
            else:
                mark_all_tracks_counted(self._tracker.tracks)
            self._start_calibration_window()
            self._transition("CALIBRATING", "Calibration started")
            return self.get_status()

    def reset_calibration(self) -> dict[str, object]:
        with self._lock:
            self.baseline_rate_per_min = None
            update_baseline_rate(baseline_rate_per_min=None)
            self.calibrating = False
            self._calibration_samples = []
            self._clear_calibration_window()
            self.operator_absent_active = False
            self._operator_absent_emitted = False
            next_state = "IDLE" if self._is_configured() and not self.monitoring_enabled else "RUNNING_GREEN"
            if not self._is_configured():
                next_state = "NOT_CONFIGURED"
            self._transition(next_state, "Calibration reset")
            return self.get_status()

    def reset_counts(self) -> dict[str, object]:
        with self._lock:
            self._clear_count_state()
            self.last_event = {
                "type": "COUNTS_RESET",
                "message": "Counts reset",
                "state_from": self.state,
                "state_to": self.state,
            }
            log_event(event_type="COUNTS_RESET", state_from=self.state, state_to=self.state, message="Counts reset")
            return self.get_status()

    def set_person_ignore_enabled(self, enabled: bool) -> dict[str, object]:
        with self._lock:
            self.person_ignore_enabled = enabled
            if not enabled:
                self._latest_person_boxes = []
            self.last_event = {
                "type": "PERSON_IGNORE_TOGGLED",
                "message": "Person ignore enabled" if enabled else "Person ignore disabled",
                "state_from": self.state,
                "state_to": self.state,
            }
            log_event(
                event_type="PERSON_IGNORE_TOGGLED",
                state_from=self.state,
                state_to=self.state,
                message="Person ignore enabled" if enabled else "Person ignore disabled",
            )
            return self.get_status()

    def adjust_count(self, delta: int) -> dict[str, object]:
        """Manual count adjustment (+/- buttons on dashboard)."""
        with self._lock:
            if delta > 0:
                for _ in range(delta):
                    self._record_count_event(count_authority=None)
            elif delta < 0:
                self.counter_state.counts_this_minute = max(0, self.counter_state.counts_this_minute + delta)
                self.counter_state.counts_this_hour = max(0, self.counter_state.counts_this_hour + delta)
                self._runtime_total = max(0, self._runtime_total + delta)
                self._current_minute_count = max(0, self._current_minute_count + delta)
            self.last_event = {
                "type": "MANUAL_ADJUST",
                "message": f"Manual count adjustment: {'+' if delta > 0 else ''}{delta}",
                "state_from": self.state,
                "state_to": self.state,
            }
            log_event(
                event_type="MANUAL_ADJUST",
                state_from=self.state,
                state_to=self.state,
                message=f"Manual count adjustment: {'+' if delta > 0 else ''}{delta}",
            )
            return self.get_status()

    def _run_loop(self) -> None:
        fps = max(1.0, get_processing_fps())
        delay = 1.0 / fps

        while not self._stop_event.is_set():
            started = time.time()
            next_delay = delay
            self._last_loop_tick_ts = started
            try:
                with self._lock:
                    configured = self._is_configured()
                    if not configured:
                        self._transition("NOT_CONFIGURED", "Setup incomplete")
                        self._write_health_sample_if_due(
                            source_kind="demo" if self.video_runtime.current_source_kind() == "demo" else "camera"
                        )

                if not configured:
                    self._sleep_remaining(started, delay)
                    continue

                runtime_status = self.video_runtime.ensure_running()
                snap = self.video_runtime.reader.snapshot()
                reader_status = self.video_runtime.reader.status()
                if snap.last_frame_time > 0:
                    with self._lock:
                        self.last_frame_age_sec = max(0.0, time.time() - snap.last_frame_time)
                        self._clear_error_if_matches("VIDEO_SOURCE_ERROR")
                        self._clear_error_if_matches("VIDEO_STALL")

                deterministic_demo = self._should_use_deterministic_demo_counting(source_is_demo=runtime_status.source.is_demo)
                if self._should_finalize_demo_playback(
                    source_is_demo=runtime_status.source.is_demo,
                    reader_status=reader_status,
                    deterministic_demo=deterministic_demo,
                ):
                    with self._lock:
                        if not deterministic_demo:
                            flushed = self._flush_demo_end_of_stream_events(
                                reader_sequence_index=int(reader_status.get("last_sequence_index") or 0),
                                reader_frame_time=float(reader_status.get("last_frame_time") or 0.0),
                                reader_source_timestamp_sec=(
                                    None
                                    if reader_status.get("last_source_timestamp_sec") is None
                                    else float(reader_status.get("last_source_timestamp_sec") or 0.0)
                                ),
                            )
                            if flushed > 0:
                                self._write_health_sample_if_due(source_kind="demo")
                                self._sleep_remaining(started, delay)
                                continue
                        self._handle_demo_playback_complete()
                        self._write_health_sample_if_due(source_kind="demo")
                    self._sleep_remaining(started, delay)
                    continue

                if self._is_video_stalled() and self._should_handle_video_stall(
                    source_is_demo=runtime_status.source.is_demo,
                    reader_status=reader_status,
                ):
                    self._handle_video_stall()
                    self._sleep_remaining(started, delay)
                    continue

                frame_snapshot = self._next_reader_frame(source_is_demo=runtime_status.source.is_demo)
                frame = None if frame_snapshot is None else frame_snapshot.frame
                if frame is None:
                    with self._lock:
                        self._write_health_sample_if_due(source_kind="demo" if runtime_status.source.is_demo else "camera")
                    self._sleep_remaining(started, delay)
                    continue

                with self._lock:
                    config = get_config()
                    roi = config.get("roi_polygon")
                    should_process = self.monitoring_enabled or self.calibrating

                if should_process:
                    if deterministic_demo:
                        increment, debug_artifact = self._run_deterministic_demo_counting(frame)
                        if increment > 0:
                            logger.info(
                                "DEMO_RECEIPT_COUNT: +%d (total hour: %d)",
                                increment,
                                self.counter_state.counts_this_hour + increment,
                            )
                        with self._lock:
                            self._latest_debug_artifact = {
                                "mode": "runtime",
                                "updated_at_ts": time.time(),
                                "source_frame": frame.copy(),
                                **debug_artifact,
                            }
                    elif self._counting_mode == "event_based":
                        increment, debug_artifact = self._run_event_based_counting(frame, roi)
                        if increment > 0:
                            logger.info("EVENT_COUNT: +%d (total hour: %d)", increment, self.counter_state.counts_this_hour + increment)
                        with self._lock:
                            self._latest_debug_artifact = {
                                "mode": "calibration" if self.calibrating else "runtime",
                                "updated_at_ts": time.time(),
                                "source_frame": frame.copy(),
                                **debug_artifact,
                            }
                    else:
                        # Track-based: existing approach
                        person_boxes = self._refresh_person_ignore_boxes(frame)
                        counting_frame = self._mask_person_regions(frame, person_boxes)
                        roi_frame = apply_roi_mask(counting_frame, roi)
                        debug_result = self._yolo_detector.detect(roi_frame)
                        detections = debug_result.detections
                        centroids = [detection.centroid for detection in detections]
                        tracks = self._tracker.update(centroids)
                        increment = count_new_tracks(
                            tracks,
                            min_track_frames=max(1, get_count_min_track_frames()),
                        )
                        with self._lock:
                            self._latest_debug_artifact = {
                                "mode": "calibration" if self.calibrating else "runtime",
                                "updated_at_ts": time.time(),
                                "source_frame": frame.copy(),
                                "roi_frame": roi_frame.copy(),
                                "mask_frame": cv2.cvtColor(debug_result.foreground_mask, cv2.COLOR_GRAY2BGR),
                                "detections": [
                                    {
                                        "bbox": detection.bbox,
                                        "centroid": detection.centroid,
                                        "area": detection.area,
                                    }
                                    for detection in detections
                                ],
                                "tracks": [
                                    {
                                        "track_id": track.track_id,
                                        "centroid": track.centroid,
                                        "counted": track.counted,
                                        "age": track.age,
                                        "frames_seen": track.frames_seen,
                                    }
                                    for track in tracks.values()
                                ],
                                "person_boxes": [dict(item) for item in person_boxes],
                            }

                    if increment > 0:
                        with self._lock:
                            count_events = list(debug_artifact.get("count_events") or [])
                            event_count_authorities = list(debug_artifact.get("event_count_authorities") or [])
                            if count_events:
                                self._record_count_events(
                                    count_events,
                                    reader_sequence_index=frame_snapshot.sequence_index,
                                    reader_frame_time=frame_snapshot.last_frame_time,
                                    source_timestamp_sec=frame_snapshot.source_timestamp_sec,
                                    source_kind="demo" if runtime_status.source.is_demo else "camera",
                                )
                            elif event_count_authorities:
                                for authority in event_count_authorities:
                                    self._record_count_event(count_authority=str(authority))
                            else:
                                for _ in range(increment):
                                    self._record_count_event(count_authority=None)
                    with self._lock:
                        self.counter_state.rollover_if_needed()
                        self._rollover_completed_minute_if_needed()
                        self._update_state_from_anomalies()
                        self._handle_recovered_from_reconnect_if_needed()
                        self._write_health_sample_if_due(source_kind="demo" if runtime_status.source.is_demo else "camera")
                else:
                    with self._lock:
                        self.counter_state.rollover_if_needed()
                        self._rollover_completed_minute_if_needed()
                        if self._is_configured() and self.state not in {"CALIBRATING", "NOT_CONFIGURED"}:
                            self._transition("IDLE", "Waiting for monitoring")
                        self._handle_recovered_from_reconnect_if_needed()
                        self._write_health_sample_if_due(source_kind="demo" if runtime_status.source.is_demo else "camera")
                next_delay = self._next_frame_pacing_delay(
                    default_delay=next_delay,
                    loop_started_ts=started,
                    source_is_demo=runtime_status.source.is_demo,
                    frame_snapshot=frame_snapshot,
                )
                pending_frames = int(self.video_runtime.reader.status().get("pending_frames") or 0)
                if self._should_drain_pending_frames_without_delay(
                    source_is_demo=runtime_status.source.is_demo,
                    pending_frames=pending_frames,
                ):
                    next_delay = 0.0
            except Exception as exc:  # noqa: BLE001
                logger.exception("Vision loop error")
                with self._lock:
                    self._record_runtime_error("VISION_LOOP_ERROR", str(exc))

            self._sleep_remaining(started, next_delay)

    def _run_event_based_counting(
        self,
        frame,
        roi: list[dict[str, float]] | None,
    ) -> tuple[int, dict[str, Any]]:
        if self._runtime_event_counter is not None:
            return self._run_runtime_event_counting(frame)

        if self._event_tracker is None:
            mask_frame = frame.copy()
            mask_frame[:] = 0
            return 0, {
                "roi_frame": frame.copy(),
                "mask_frame": mask_frame,
                "detections": [],
                "clustered_centroids": [],
                "tracks": [],
                "person_boxes": [],
                "count_events": [],
                "event_count_rule": self._event_count_rule,
                "event_count_rule_config_error": self._event_count_rule_config_error,
            }

        roi_frame = apply_roi_mask(frame, roi) if roi else frame
        debug_result = self._yolo_detector.detect(roi_frame)
        detections = debug_result.detections
        centroids = self._cluster_event_detection_centroids([det.centroid for det in detections])
        if centroids:
            logger.debug("EVENT_DETECT: %d detections this frame", len(centroids))
        dead_tracks, active_tracks = self._event_tracker.update_with_dead(centroids) if self._event_tracker is not None else ([], {})
        min_track_frames = max(1, get_event_track_min_frames())
        min_travel_px = max(0.0, get_event_track_min_travel_px())
        increment = count_dead_tracks(
            dead_tracks,
            min_track_frames=min_track_frames,
            min_travel_px=min_travel_px,
        )
        count_events = [
            {
                "track_id": track.track_id,
                "count": 1,
                "reason": "dead_track_event",
                "bbox": None,
                "centroid": list(track.centroid),
                "first_centroid": list(track.first_centroid),
                "travel_px": round(track_travel_px(track), 3),
                "frames_seen": track.frames_seen,
                "count_authority": "runtime_inferred_only",
            }
            for track in dead_tracks
            if track.frames_seen >= min_track_frames and track_travel_px(track) >= min_travel_px
        ]
        return increment, {
            "roi_frame": roi_frame.copy(),
            "mask_frame": cv2.cvtColor(debug_result.foreground_mask, cv2.COLOR_GRAY2BGR),
            "detections": [
                {
                    "bbox": detection.bbox,
                    "centroid": detection.centroid,
                    "area": detection.area,
                }
                for detection in detections
            ],
            "clustered_centroids": centroids,
            "tracks": [
                {
                    "track_id": track.track_id,
                    "centroid": track.centroid,
                    "counted": track.counted,
                    "age": track.age,
                    "frames_seen": track.frames_seen,
                }
                for track in active_tracks.values()
            ],
            "person_boxes": [],
            "count_events": count_events,
            "event_count_rule": self._event_count_rule,
            "event_count_rule_config_error": self._event_count_rule_config_error,
        }

    def _cluster_event_detection_centroids(self, centroids: list[tuple[int, int]]) -> list[tuple[int, int]]:
        max_distance = get_event_detection_cluster_distance()
        if max_distance <= 0 or len(centroids) < 2:
            return centroids

        parents = list(range(len(centroids)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parents[root_right] = root_left

        max_distance_sq = max_distance * max_distance
        for left, left_centroid in enumerate(centroids):
            for right in range(left + 1, len(centroids)):
                right_centroid = centroids[right]
                dx = left_centroid[0] - right_centroid[0]
                dy = left_centroid[1] - right_centroid[1]
                if (dx * dx) + (dy * dy) <= max_distance_sq:
                    union(left, right)

        grouped_indices: dict[int, list[int]] = {}
        for index in range(len(centroids)):
            grouped_indices.setdefault(find(index), []).append(index)

        clustered: list[tuple[int, int]] = []
        for indices in sorted(grouped_indices.values(), key=lambda values: min(values)):
            x = round(sum(centroids[index][0] for index in indices) / len(indices))
            y = round(sum(centroids[index][1] for index in indices) / len(indices))
            clustered.append((int(x), int(y)))
        return clustered

    def _run_runtime_event_counting(self, frame) -> tuple[int, dict[str, Any]]:
        debug_result = self._yolo_detector.detect(frame)
        detections = [{"box": detection.bbox, "confidence": 1.0} for detection in debug_result.detections]
        if detections:
            logger.debug("EVENT_RUNTIME_DETECT: %d detections this frame", len(detections))
        person_boxes = self._refresh_runtime_person_boxes(frame)
        frame_result = self._runtime_event_counter.process_frame(
            frame=frame,
            detections=detections,
            person_boxes=person_boxes,
        )
        counted_track_ids = {event.track_id for event in frame_result.events}
        event_count_authorities = [event.count_authority for event in frame_result.events]
        return len(frame_result.events), {
            "roi_frame": frame.copy(),
            "mask_frame": cv2.cvtColor(debug_result.foreground_mask, cv2.COLOR_GRAY2BGR),
            "detections": [
                {
                    "bbox": detection.bbox,
                    "centroid": detection.centroid,
                    "area": detection.area,
                }
                for detection in debug_result.detections
            ],
            "tracks": [
                {
                    "track_id": track.track_id,
                    "bbox": track.bbox,
                    "centroid": box_center(track.bbox),
                    "counted": track.track_id in counted_track_ids,
                    "confidence": track.confidence,
                    "perception_gate": self._gate_decision_payload(frame_result.gate_decisions.get(track.track_id)),
                }
                for track in frame_result.tracks
            ],
            "person_boxes": [self._person_box_payload(item) for item in person_boxes],
            "event_count_authorities": event_count_authorities,
            "count_events": self._runtime_count_event_payloads(frame_result),
            "event_count_rule": self._event_count_rule,
            "event_count_rule_config_error": self._event_count_rule_config_error,
        }

    def _next_reader_frame(self, *, source_is_demo: bool):
        reader = self.video_runtime.reader
        if source_is_demo and reader.is_synchronous_demo_mode():
            return reader.pump_next_demo_frame()
        return reader.consume_next_frame()

    def _run_deterministic_demo_counting(self, frame) -> tuple[int, dict[str, Any]]:
        if self._deterministic_demo_runner is None:
            return 0, self._build_deterministic_demo_artifact(frame, [])
        if not self._deterministic_demo_runner.active:
            self._deterministic_demo_runner.activate()
        revealed_events = self._deterministic_demo_runner.drain_due_events()
        return len(revealed_events), self._build_deterministic_demo_artifact(frame, revealed_events)

    def _build_deterministic_demo_artifact(self, frame, revealed_events: list[dict[str, Any]]) -> dict[str, Any]:
        mask_frame = frame.copy()
        mask_frame[:] = 0
        tracks = []
        for event in revealed_events:
            bbox = event.get("bbox") or []
            bbox_tuple = tuple(float(value) for value in bbox) if len(bbox) == 4 else None
            tracks.append(
                {
                    "track_id": int(event.get("track_id") or 0),
                    "bbox": bbox_tuple,
                    "centroid": box_center(bbox_tuple) if bbox_tuple is not None else None,
                    "counted": True,
                    "confidence": 1.0,
                    "perception_gate": event.get("gate_decision"),
                }
            )
        return {
            "roi_frame": frame.copy(),
            "mask_frame": mask_frame,
            "detections": [],
            "tracks": tracks,
            "person_boxes": [],
            "event_count_authorities": [
                str(event["count_authority"])
                for event in revealed_events
                if event.get("count_authority") is not None
            ],
        }

    def _run_person_loop(self) -> None:
        detect_interval = 1.0 / max(0.1, get_person_detect_fps())
        while not self._stop_event.is_set():
            started = time.time()
            self._last_person_loop_tick_ts = started
            try:
                if not self._should_run_person_detection():
                    self._handle_person_recovered_if_needed()
                else:
                    self.video_runtime.ensure_running()
                    snap = self.video_runtime.reader.snapshot()
                    if snap.frame is not None:
                        self._run_operator_presence_detection(snap.frame)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Person detection loop error")
                with self._lock:
                    self._record_runtime_error("PERSON_LOOP_ERROR", str(exc))

            self._sleep_remaining(started, detect_interval)

    def _should_run_person_detection(self) -> bool:
        with self._lock:
            if self.baseline_rate_per_min is None:
                return False
            if self.state != "RUNNING_YELLOW_DROP":
                return False
            cfg = get_config()
            operator_zone = cfg.get("operator_zone") or {}
            return bool(operator_zone.get("enabled") and operator_zone.get("polygon"))

    def _run_operator_presence_detection(self, frame) -> None:
        cfg = get_config()
        operator_zone = cfg.get("operator_zone") or {}
        polygon_norm = operator_zone.get("polygon") or []
        if len(polygon_norm) < 3:
            return

        h, w = frame.shape[:2]
        polygon_px = [(int(p["x"] * w), int(p["y"] * h)) for p in polygon_norm]

        detector = self._ensure_person_detector()
        detections = detector.detect_people(frame) if detector else []
        person_in_zone = False
        for det in detections:
            cx = det.x + det.w // 2
            cy = det.y + det.h // 2
            if point_in_polygon((cx, cy), polygon_px):
                person_in_zone = True
                break

        now = time.time()
        with self._lock:
            if person_in_zone:
                self._operator_last_seen_ts = now
                if self.operator_absent_active:
                    prev_absent_state = self.state
                    self.operator_absent_active = False
                    self._operator_absent_emitted = False
                    recover_state = self._state_before_operator_absent or "RUNNING_YELLOW_DROP"
                    self.last_event = {
                        "type": "RECOVERED",
                        "message": "Person returned to operator zone",
                        "state_from": prev_absent_state,
                        "state_to": recover_state,
                    }
                    log_event(
                        event_type="RECOVERED",
                        state_from=prev_absent_state,
                        state_to=recover_state,
                        message="Person returned to operator zone",
                    )
                    self._transition(recover_state, "Operator returned")
                return

            absent_minutes = max(1, get_operator_absent_minutes())
            if self._operator_last_seen_ts is None:
                self._operator_last_seen_ts = now
                return

            if now - self._operator_last_seen_ts >= absent_minutes * 60 and not self._operator_absent_emitted:
                self._operator_absent_emitted = True
                self.operator_absent_active = True
                self._state_before_operator_absent = self.state
                self.last_event = {
                    "type": "OPERATOR_ABSENT",
                    "message": f"No person in operator zone for {absent_minutes} minute(s)",
                    "state_from": self.state,
                    "state_to": "RUNNING_RED_STOPPED",
                }
                log_event(
                    event_type="OPERATOR_ABSENT",
                    state_from=self.state,
                    state_to="RUNNING_RED_STOPPED",
                    message=f"No person in operator zone for {absent_minutes} minute(s)",
                )
                self._transition("RUNNING_RED_STOPPED", "Operator absent during drop")

    def _handle_person_recovered_if_needed(self) -> None:
        with self._lock:
            if not self.operator_absent_active:
                return
            # Keep absence state latched until person appears in zone again during gated detection.
            self._transition("RUNNING_RED_STOPPED", "Operator absent during drop")

    def _sleep_remaining(self, started: float, target_delay: float) -> None:
        elapsed = time.time() - started
        remaining = target_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _next_frame_pacing_delay(
        self,
        *,
        default_delay: float,
        loop_started_ts: float,
        source_is_demo: bool,
        frame_snapshot,
    ) -> float:
        if not source_is_demo or not self.video_runtime.reader.is_synchronous_demo_mode():
            return default_delay
        return 0.0

    def _should_drain_pending_frames_without_delay(self, *, source_is_demo: bool, pending_frames: int) -> bool:
        if pending_frames <= 0:
            return False
        if source_is_demo and self.video_runtime.reader.is_synchronous_demo_mode():
            return False
        return True

    def _minute_key_now(self) -> tuple[int, int, int, int, int]:
        now = datetime.now()
        return (now.year, now.month, now.day, now.hour, now.minute)

    def _rollover_completed_minute_if_needed(self) -> None:
        key_now = self._minute_key_now()
        if key_now == self._current_minute_key:
            return

        completed_count = self._current_minute_count
        self._minute_history.append(completed_count)
        self._current_minute_count = 0
        self._current_minute_key = key_now

        if self.calibrating:
            self._calibration_samples.append(completed_count)
            target_samples = max(1, get_calibration_minutes())
            if len(self._calibration_samples) >= target_samples:
                self.baseline_rate_per_min = float(statistics.median(self._calibration_samples))
                update_baseline_rate(baseline_rate_per_min=self.baseline_rate_per_min)
                self.calibrating = False
                self._clear_calibration_window()
                self._transition("RUNNING_GREEN", f"Calibration complete: baseline={self.baseline_rate_per_min:.2f}")

        window = max(1, get_drop_minutes())
        sample = list(self._minute_history)[-window:]
        self.rolling_rate_per_min = float(sum(sample) / len(sample)) if sample else 0.0

    def _update_state_from_anomalies(self) -> None:
        if self.calibrating:
            self._transition("CALIBRATING", "Calibration in progress")
            return

        if self.operator_absent_active:
            self._transition("RUNNING_RED_STOPPED", "Operator absent during drop")
            return

        if not self.monitoring_enabled:
            if self._is_configured():
                self._transition("IDLE", "Monitoring disabled")
            return

        stop_n = max(1, get_stop_minutes())
        recent = list(self._minute_history)[-stop_n:]
        if len(recent) >= stop_n and sum(recent) == 0:
            self._transition("RUNNING_RED_STOPPED", f"Stop detected: zero count for {stop_n} minute(s)")
            return

        drop_m = max(1, get_drop_minutes())
        if self.baseline_rate_per_min and self.baseline_rate_per_min > 0:
            recent_drop = list(self._minute_history)[-drop_m:]
            if len(recent_drop) >= drop_m:
                rolling = sum(recent_drop) / len(recent_drop)
                threshold = self.baseline_rate_per_min * get_drop_threshold()
                if rolling < threshold:
                    self._transition("RUNNING_YELLOW_DROP", f"Drop detected: rolling={rolling:.2f}, threshold={threshold:.2f}")
                    return

        self._transition("RUNNING_GREEN", "Running normally")

    def _transition(self, next_state: str, message: str) -> None:
        if self.state == next_state:
            return
        prev = self.state
        self.state = next_state
        self.last_event = {"type": "STATE_TRANSITION", "message": message, "state_from": prev, "state_to": next_state}
        log_event(event_type="STATE_TRANSITION", state_from=prev, state_to=next_state, message=message)

    def _is_configured(self) -> bool:
        cfg = get_config()
        has_roi = bool(cfg.get("roi_polygon"))
        if is_demo_mode():
            if self._counting_mode == "event_based":
                return True  # ROI optional in event mode
            return has_roi
        has_camera = bool(cfg.get("camera_ip") and cfg.get("camera_username") and cfg.get("camera_password"))
        if self._counting_mode == "event_based":
            return has_camera  # ROI optional in event mode
        return has_camera and has_roi

    def _should_use_deterministic_demo_counting(self, *, source_is_demo: bool) -> bool:
        return bool(
            source_is_demo
            and self._counting_mode == "event_based"
            and self._runtime_calibration_path is not None
            and self._demo_count_mode == "deterministic_file_runner"
            and self._deterministic_demo_runner is not None
        )

    def _record_count_event(self, *, count_authority: str | None = "source_token_authorized") -> None:
        self.counter_state.increment()
        self._runtime_total += 1
        self._current_minute_count += 1
        if count_authority == "source_token_authorized":
            self._proof_backed_total += 1
        elif count_authority == "runtime_inferred_only":
            self._runtime_inferred_only_total += 1
        record_count_event(timestamp=datetime.now(), count_source="vision", increment=1)

    def _record_count_events(
        self,
        count_events: list[dict[str, Any]],
        *,
        reader_sequence_index: int,
        reader_frame_time: float,
        source_timestamp_sec: float | None,
        source_kind: str,
    ) -> None:
        for count_event in count_events:
            if (
                str(count_event.get("reason") or "") == "dead_track_event"
                and source_timestamp_sec is not None
                and self._should_debounce_event_based_count(float(source_timestamp_sec))
            ):
                continue
            authority = count_event.get("count_authority")
            self._record_count_event(count_authority=None if authority is None else str(authority))
            if str(count_event.get("reason") or "") == "dead_track_event" and source_timestamp_sec is not None:
                self._last_event_based_count_source_ts = float(source_timestamp_sec)
            traced_event = dict(count_event)
            traced_event["event_ts"] = round(float(source_timestamp_sec), 3) if source_timestamp_sec is not None else None
            traced_event["runtime_total_after_event"] = self._runtime_total
            traced_event["proof_backed_total_after_event"] = self._proof_backed_total
            traced_event["runtime_inferred_only_after_event"] = self._runtime_inferred_only_total
            traced_event["reader_frame_sequence_index"] = reader_sequence_index
            traced_event["reader_frame_time"] = round(reader_frame_time, 6) if reader_frame_time > 0 else 0.0
            traced_event["source_kind"] = source_kind
            traced_event["worker_state"] = self.state
            self._recent_count_events.append(traced_event)

    def _should_debounce_event_based_count(self, source_timestamp_sec: float) -> bool:
        debounce_sec = max(0.0, get_event_count_debounce_sec())
        if debounce_sec <= 0 or self._last_event_based_count_source_ts is None:
            return False
        return source_timestamp_sec - self._last_event_based_count_source_ts < debounce_sec

    def _runtime_count_event_payloads(self, frame_result) -> list[dict[str, Any]]:
        return [
            {
                "track_id": event.track_id,
                "count": event.count,
                "reason": event.reason,
                "bbox": list(event.bbox),
                "source_track_id": event.source_track_id,
                "source_token_id": event.source_token_id,
                "chain_id": event.chain_id,
                "source_bbox": None if event.source_bbox is None else list(event.source_bbox),
                "provenance_status": event.provenance_status,
                "count_authority": event.count_authority,
                "track_zone": frame_result.track_zones.get(event.track_id),
                "person_overlap_ratio": float(frame_result.track_metadata.get(event.track_id, {}).get("person_overlap_ratio", 0.0)),
                "outside_person_ratio": float(frame_result.track_metadata.get(event.track_id, {}).get("outside_person_ratio", 1.0)),
                "predecessor_chain_track_ids": list(frame_result.event_provenance.get(event.track_id, {}).get("predecessor_chain_track_ids", [])),
            }
            for event in frame_result.events
        ]

    def _flush_demo_end_of_stream_events(
        self,
        *,
        reader_sequence_index: int,
        reader_frame_time: float,
        reader_source_timestamp_sec: float | None = None,
    ) -> int:
        if self._demo_eof_flush_applied:
            self._demo_eof_flush_applied = True
            return 0
        self._demo_eof_flush_applied = True
        if self._runtime_event_counter is not None:
            frame_result = self._runtime_event_counter.flush_end_of_stream(iterations=2)
            count_events = self._runtime_count_event_payloads(frame_result)
        elif self._event_tracker is not None:
            min_track_frames = max(1, get_event_track_min_frames())
            count_events = []
            for track in self._event_tracker.tracks.values():
                if track.counted or track.frames_seen < min_track_frames:
                    continue
                track.counted = True
                count_events.append(
                    {
                        "track_id": track.track_id,
                        "count": 1,
                        "reason": "end_of_stream_active_track_event",
                        "bbox": None,
                        "centroid": list(track.centroid),
                        "frames_seen": track.frames_seen,
                        "count_authority": "runtime_inferred_only",
                    }
                )
        else:
            count_events = []
        if not count_events:
            return 0
        self._record_count_events(
            count_events,
            reader_sequence_index=reader_sequence_index,
            reader_frame_time=reader_frame_time,
            source_timestamp_sec=reader_source_timestamp_sec,
            source_kind="demo",
        )
        return len(count_events)

    def _clear_count_state(self) -> None:
        self.counter_state = CounterState()
        self._runtime_total = 0
        self._proof_backed_total = 0
        self._runtime_inferred_only_total = 0
        self._current_minute_count = 0
        self._current_minute_key = self._minute_key_now()
        self._minute_history.clear()
        self._recent_count_events.clear()
        self._last_event_based_count_source_ts = None
        self._demo_eof_flush_applied = False
        self.rolling_rate_per_min = 0.0
        if self._runtime_event_counter is not None:
            self._runtime_event_counter.reset()
        elif self._event_tracker is not None:
            self._event_tracker = CentroidTracker(
                max_age_frames=get_event_track_max_age(),
                max_match_distance=get_event_track_max_match_distance(),
            )
        if self._deterministic_demo_runner is not None:
            self._deterministic_demo_runner.disarm()
        clear_count_history()

    def _start_calibration_window(self) -> None:
        start_ts = time.time()
        start_dt = datetime.fromtimestamp(start_ts)
        next_minute_boundary = start_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        target_samples = max(1, get_calibration_minutes())
        deadline_dt = next_minute_boundary + timedelta(minutes=target_samples - 1)
        self._calibration_started_at_ts = start_ts
        self._calibration_deadline_ts = deadline_dt.timestamp()

    def _clear_calibration_window(self) -> None:
        self._calibration_started_at_ts = None
        self._calibration_deadline_ts = None

    def _get_calibration_target_duration_sec(self) -> int:
        if self._calibration_started_at_ts is not None and self._calibration_deadline_ts is not None:
            return max(1, int(round(self._calibration_deadline_ts - self._calibration_started_at_ts)))
        return max(60, get_calibration_minutes() * 60)

    def _get_calibration_elapsed_sec(self) -> int:
        target_duration_sec = self._get_calibration_target_duration_sec()
        if self.baseline_rate_per_min is not None and not self.calibrating:
            return target_duration_sec
        if self._calibration_started_at_ts is None:
            return 0
        elapsed_sec = max(0.0, time.time() - self._calibration_started_at_ts)
        return min(target_duration_sec, int(elapsed_sec))

    def _get_calibration_progress_pct(self) -> int:
        if self.baseline_rate_per_min is not None and not self.calibrating:
            return 100
        if not self.calibrating or self._calibration_started_at_ts is None or self._calibration_deadline_ts is None:
            return 0
        duration_sec = max(1.0, self._calibration_deadline_ts - self._calibration_started_at_ts)
        elapsed_sec = max(0.0, time.time() - self._calibration_started_at_ts)
        return max(1, min(99, int(round((elapsed_sec / duration_sec) * 100))))

    def _record_runtime_error(self, error_code: str, message: str) -> None:
        self.last_error_code = error_code
        self.last_error_message = message
        key = (error_code, message)
        now = time.time()
        if self._last_error_emit_key == key and (now - self._last_error_emit_ts) < 30:
            return
        self._last_error_emit_key = key
        self._last_error_emit_ts = now
        log_event(event_type="ERROR", state_from=self.state, state_to=self.state, message=f"{error_code}: {message}")

    def _clear_error_if_matches(self, error_code: str) -> None:
        if self.last_error_code == error_code:
            self.last_error_code = None
            self.last_error_message = None

    def _is_video_stalled(self) -> bool:
        if self.last_frame_age_sec is None:
            return False
        return self.last_frame_age_sec > get_frame_stall_timeout_sec()

    def _handle_video_stall(self) -> None:
        previous_state = self.state
        if previous_state != "RUNNING_YELLOW_RECONNECTING":
            self.last_event = {
                "type": "RECONNECTING",
                "message": "Video stalled, reconnecting",
                "state_from": previous_state,
                "state_to": "RUNNING_YELLOW_RECONNECTING",
            }
            log_event(
                event_type="RECONNECTING",
                state_from=previous_state,
                state_to="RUNNING_YELLOW_RECONNECTING",
                message="Video stalled, reconnecting",
            )
        self.state = "RUNNING_YELLOW_RECONNECTING"
        self.reconnect_attempts_total += 1
        self._was_reconnecting = True
        self._record_runtime_error("VIDEO_STALL", "Video frames became stale")
        logger.warning("Video stalled, restarting runtime")
        try:
            self.video_runtime.restart()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video runtime restart failed")
            self._record_runtime_error("VIDEO_SOURCE_ERROR", str(exc))
        time.sleep(self._reconnect_backoff_sec)
        self._reconnect_backoff_sec = min(self._reconnect_backoff_sec * 2, get_reconnect_backoff_max_sec())

    def _handle_recovered_from_reconnect_if_needed(self) -> None:
        if not self._was_reconnecting or self.state == "RUNNING_YELLOW_RECONNECTING":
            return
        self.last_event = {
            "type": "RECONNECTED",
            "message": "Video reconnected",
            "state_from": "RUNNING_YELLOW_RECONNECTING",
            "state_to": self.state,
        }
        log_event(
            event_type="RECONNECTED",
            state_from="RUNNING_YELLOW_RECONNECTING",
            state_to=self.state,
            message="Video reconnected",
        )
        self._was_reconnecting = False
        self._reconnect_backoff_sec = max(0.1, get_reconnect_backoff_initial_sec())

    def _handle_demo_playback_complete(self) -> None:
        if not (self.monitoring_enabled or self.calibrating or self._runtime_total > 0):
            return
        if self._deterministic_demo_runner is not None:
            self._deterministic_demo_runner.freeze()
        self.monitoring_enabled = False
        self.calibrating = False
        self.operator_absent_active = False
        self._operator_absent_emitted = False
        self.last_frame_age_sec = 0.0
        self._transition("DEMO_COMPLETE", "Demo playback complete")

    def _should_finalize_demo_playback(
        self,
        *,
        source_is_demo: bool,
        reader_status: dict[str, object],
        deterministic_demo: bool,
    ) -> bool:
        if not source_is_demo or not reader_status.get("demo_finished"):
            return False
        if int(reader_status.get("pending_frames") or 0) > 0:
            return False
        if not deterministic_demo or self._deterministic_demo_runner is None:
            return True
        return self._deterministic_demo_runner.is_finished

    def _should_handle_video_stall(
        self,
        *,
        source_is_demo: bool,
        reader_status: dict[str, object],
    ) -> bool:
        if source_is_demo and self.video_runtime.reader.is_synchronous_demo_mode():
            return bool(self.monitoring_enabled or self.calibrating)
        return not (source_is_demo and bool(reader_status.get("demo_finished")))

    def _write_health_sample_if_due(self, *, source_kind: str) -> None:
        now = time.time()
        if (now - self._last_health_sample_ts) < get_health_sample_interval_sec():
            return
        self._last_health_sample_ts = now
        reader_status = self.video_runtime.reader.status()
        insert_health_sample(
            sample={
                "current_state": self.state,
                "last_frame_age_sec": self.last_frame_age_sec,
                "reconnect_attempts_total": self.reconnect_attempts_total,
                "reader_alive": reader_status["thread_alive"],
                "vision_loop_alive": bool(self._thread and self._thread.is_alive()),
                "person_detect_loop_alive": bool(self._person_thread and self._person_thread.is_alive()),
                "source_kind": source_kind,
                "rolling_rate_per_min": self.rolling_rate_per_min,
                "baseline_rate_per_min": self.baseline_rate_per_min,
                "counts_this_minute": self.counter_state.counts_this_minute,
                "counts_this_hour": self.counter_state.counts_this_hour,
                "runtime_total": self._runtime_total,
                "proof_backed_total": self._proof_backed_total,
                "runtime_inferred_only": self._runtime_inferred_only_total,
                "last_error_code": self.last_error_code,
                "last_error_message": self.last_error_message,
            }
        )

    def get_diagnostics(self, *, uptime_sec: float, db_path: str, log_directory: str) -> dict[str, object]:
        reader_status = self.video_runtime.reader.status()
        latest_error_message = self.last_error_message or reader_status.get("last_error")
        source_kind = self.video_runtime.current_source_kind()
        demo_active = bool(source_kind == "demo" and (self.monitoring_enabled or self.calibrating) and not self.video_runtime.is_demo_finished())
        demo_elapsed = 0.0 if self._deterministic_demo_runner is None else round(self._deterministic_demo_runner.current_elapsed_sec(), 2)
        return {
            "app_version": "0.1.0",
            "uptime_sec": round(uptime_sec, 2),
            "current_state": self.state,
            "count_source": "vision",
            "last_frame_age_sec": None if self.last_frame_age_sec is None else round(self.last_frame_age_sec, 2),
            "reconnect_attempts_total": self.reconnect_attempts_total,
            "reader_alive": bool(reader_status["thread_alive"]),
            "vision_loop_alive": bool(self._thread and self._thread.is_alive()),
            "person_detect_loop_alive": bool(self._person_thread and self._person_thread.is_alive()),
            "db_path": db_path,
            "log_directory": log_directory,
            "source_kind": source_kind,
            "demo_playback_speed": round(self.video_runtime.current_demo_playback_speed(), 2),
            "demo_video_name": self.video_runtime.current_demo_video_name(),
            "demo_count_mode": self._demo_count_mode,
            "demo_loop_enabled": self.video_runtime.is_demo_loop_enabled(),
            "demo_playback_finished": self.video_runtime.is_demo_finished(),
            "demo_elapsed_sec": demo_elapsed,
            "demo_playback_active": demo_active,
            "reader_last_sequence_index": int(reader_status.get("last_sequence_index") or 0),
            "reader_last_source_timestamp_sec": (
                None
                if reader_status.get("last_source_timestamp_sec") is None
                else round(float(reader_status.get("last_source_timestamp_sec")), 3)
            ),
            "demo_receipt_total": 0 if self._deterministic_demo_runner is None else self._deterministic_demo_runner.receipt_count,
            "demo_revealed_receipts": 0 if self._deterministic_demo_runner is None else self._deterministic_demo_runner.revealed_count,
            "demo_expected_final_total": 0 if self._deterministic_demo_runner is None else self._deterministic_demo_runner.expected_final_count,
            "demo_count_report": None
            if self._deterministic_demo_runner is None or self._deterministic_demo_runner.report_path is None
            else str(self._deterministic_demo_runner.report_path),
            "person_ignore_enabled": self.person_ignore_enabled,
            "people_detected_count": len(self._latest_person_boxes),
            "counting_mode": self._counting_mode,
            "event_count_rule": self._event_count_rule,
            "event_count_rule_config_error": self._event_count_rule_config_error,
            "runtime_calibration_path": None if self._runtime_calibration_path is None else str(self._runtime_calibration_path),
            "latest_error_code": self.last_error_code,
            "latest_error_message": latest_error_message,
            "recent_count_events": [dict(item) for item in self._recent_count_events],
        }

    def _ensure_person_detector(self) -> PersonDetector | None:
        if self._person_detector is not None:
            return self._person_detector
        try:
            self._person_detector = PersonDetector(get_person_conf_threshold())
            return self._person_detector
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unable to initialize person detector")
            with self._lock:
                self._record_runtime_error("PERSON_DETECTOR_INIT_ERROR", str(exc))
            return None

    def _refresh_person_ignore_boxes(self, frame) -> list[dict[str, int | float]]:
        with self._lock:
            enabled = self.person_ignore_enabled
            last_boxes = [dict(item) for item in self._latest_person_boxes]

        if not enabled:
            return []

        interval = 1.0 / max(0.1, get_person_ignore_fps())
        now = time.time()
        if (now - self._last_person_ignore_detect_ts) < interval:
            return last_boxes

        # Use the shared YOLO detector for person detection too
        boxes = self._yolo_detector.detect_people(frame)
        with self._lock:
            self._latest_person_boxes = boxes
            self._last_person_ignore_detect_ts = now
        return [dict(item) for item in boxes]

    def _refresh_runtime_person_boxes(self, frame) -> list[Box]:
        detector = self._ensure_person_detector()
        if detector is None:
            return []

        interval = 1.0 / max(0.1, get_person_detect_fps())
        now = time.time()
        with self._lock:
            cached_payload = [dict(item) for item in self._latest_person_boxes]
            last_detect_ts = self._last_runtime_person_detect_ts
        if last_detect_ts > 0.0 and (now - last_detect_ts) < interval:
            return [
                (
                    float(item["x"]),
                    float(item["y"]),
                    float(item["w"]),
                    float(item["h"]),
                )
                for item in cached_payload
            ]

        detections = detector.detect_people(frame)
        payload = [
            {
                "x": int(det.x),
                "y": int(det.y),
                "w": int(det.w),
                "h": int(det.h),
                "confidence": float(det.confidence),
            }
            for det in detections
        ]
        with self._lock:
            self._latest_person_boxes = payload
            self._last_runtime_person_detect_ts = now
        return [
            (
                float(item["x"]),
                float(item["y"]),
                float(item["w"]),
                float(item["h"]),
            )
            for item in payload
        ]

    def _mask_person_regions(self, frame, person_boxes: list[dict[str, int | float]]) -> cv2.typing.MatLike:
        if not person_boxes:
            return frame

        masked = frame.copy()
        height, width = masked.shape[:2]
        for box in person_boxes:
            padding = 12
            x = max(0, int(box.get("x", 0)) - padding)
            y = max(0, int(box.get("y", 0)) - padding)
            w = int(box.get("w", 0)) + padding * 2
            h = int(box.get("h", 0)) + padding * 2
            x2 = min(width, x + max(0, w))
            y2 = min(height, y + max(0, h))
            cv2.rectangle(masked, (x, y), (x2, y2), color=(0, 0, 0), thickness=-1)
        return masked

    def _gate_decision_payload(self, decision: GateDecision | None) -> dict[str, Any] | None:
        if decision is None:
            return None
        return {
            "track_id": decision.track_id,
            "decision": decision.decision,
            "reason": decision.reason,
            "flags": list(decision.flags),
            "evidence": dict(decision.evidence),
        }

    def _person_box_payload(self, box: Box) -> dict[str, int]:
        x, y, w, h = box
        return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
