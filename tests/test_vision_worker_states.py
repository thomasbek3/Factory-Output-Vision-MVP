from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from app.db.config_repo import update_roi_polygon
from app.db.database import init_db
from app.services.count_state_machine import CountEvent, TrackDetection
from app.services.counting import DetectedObject, DetectionDebugResult, Track, count_new_tracks, mark_all_tracks_counted
from app.services.perception_gate import GateDecision
from app.services.runtime_event_counter import RuntimeFrameResult
from app.services.video_runtime import VideoRuntime
from app.workers.vision_worker import VisionWorker
from tests.helpers import reset_logging_for_tests


class VisionWorkerStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="factory_counter_worker_")
        self.previous_env = {
            "FC_DB_PATH": os.environ.get("FC_DB_PATH"),
            "FC_LOG_DIR": os.environ.get("FC_LOG_DIR"),
            "FC_DEMO_MODE": os.environ.get("FC_DEMO_MODE"),
            "FC_DEMO_VIDEO_PATH": os.environ.get("FC_DEMO_VIDEO_PATH"),
            "FC_PERSON_DETECT_ENABLED": os.environ.get("FC_PERSON_DETECT_ENABLED"),
            "FC_COUNTING_MODE": os.environ.get("FC_COUNTING_MODE"),
            "FC_RUNTIME_CALIBRATION_PATH": os.environ.get("FC_RUNTIME_CALIBRATION_PATH"),
        }
        os.environ["FC_DB_PATH"] = os.path.join(self.temp_dir, "worker.db")
        os.environ["FC_LOG_DIR"] = os.path.join(self.temp_dir, "logs")
        os.environ["FC_DEMO_MODE"] = "1"
        os.environ["FC_DEMO_VIDEO_PATH"] = os.path.abspath("demo/demo.mp4")
        os.environ["FC_PERSON_DETECT_ENABLED"] = "0"
        reset_logging_for_tests()
        init_db()
        update_roi_polygon(roi_polygon=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}])
        self.worker = VisionWorker(VideoRuntime())

    def tearDown(self) -> None:
        self.worker.stop()
        reset_logging_for_tests()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calibration_and_monitoring_transitions(self) -> None:
        calibrating = self.worker.start_calibration()
        self.assertEqual(calibrating["state"], "CALIBRATING")
        self.assertGreater(calibrating["calibration_target_duration_sec"], 0)
        self.assertGreaterEqual(calibrating["calibration_progress_pct"], 1)

        self.worker._calibration_started_at_ts = time.time() - 15
        self.worker._calibration_deadline_ts = time.time() + 45
        in_progress = self.worker.get_status()
        self.assertGreaterEqual(in_progress["calibration_progress_pct"], 1)
        self.assertLessEqual(in_progress["calibration_progress_pct"], 99)
        self.assertGreater(in_progress["calibration_elapsed_sec"], 0)

        self.worker.baseline_rate_per_min = 12.0
        self.worker.calibrating = False
        self.worker._clear_calibration_window()
        running = self.worker.start_monitoring()
        self.assertEqual(running["state"], "RUNNING_GREEN")
        self.assertEqual(running["calibration_progress_pct"], 100)

        stopped = self.worker.stop_monitoring()
        self.assertEqual(stopped["state"], "IDLE")

        reset = self.worker.reset_calibration()
        self.assertEqual(reset["state"], "IDLE")
        self.assertIsNone(self.worker.baseline_rate_per_min)

    def test_drop_and_stop_state_logic(self) -> None:
        self.worker.monitoring_enabled = True
        self.worker.baseline_rate_per_min = 10.0

        self.worker._minute_history = deque([0, 0], maxlen=120)
        self.worker._update_state_from_anomalies()
        self.assertEqual(self.worker.state, "RUNNING_RED_STOPPED")

        self.worker.state = "IDLE"
        self.worker._minute_history = deque([1, 1, 1], maxlen=120)
        self.worker._update_state_from_anomalies()
        self.assertEqual(self.worker.state, "RUNNING_YELLOW_DROP")

    def test_reconnect_state_logic(self) -> None:
        restart_calls: list[str] = []

        def fake_restart() -> None:
            restart_calls.append("restart")

        self.worker.video_runtime.restart = fake_restart  # type: ignore[method-assign]
        self.worker.state = "RUNNING_GREEN"
        self.worker.last_frame_age_sec = 5.0
        self.worker._reconnect_backoff_sec = 0.01

        self.worker._handle_video_stall()
        self.assertEqual(self.worker.state, "RUNNING_YELLOW_RECONNECTING")
        self.assertGreaterEqual(self.worker.reconnect_attempts_total, 1)
        self.assertEqual(self.worker.last_error_code, "VIDEO_STALL")
        self.assertEqual(restart_calls, ["restart"])

        self.worker.state = "RUNNING_GREEN"
        self.worker._handle_recovered_from_reconnect_if_needed()
        self.assertFalse(self.worker._was_reconnecting)
        self.assertEqual(self.worker.last_event["type"], "RECONNECTED")

    def test_count_new_tracks_requires_min_frames(self) -> None:
        """Tracks below min_track_frames should not be counted."""
        young_track = Track(
            track_id=1,
            centroid=(52, 50),
            first_centroid=(49, 50),
            previous_centroid=(49, 50),
            age=0,
            frames_seen=2,
            last_side=None,
            counted=False,
        )
        count = count_new_tracks({1: young_track}, min_track_frames=5)
        self.assertEqual(count, 0)
        self.assertFalse(young_track.counted)

        mature_track = Track(
            track_id=2,
            centroid=(80, 50),
            first_centroid=(20, 50),
            previous_centroid=(48, 50),
            age=0,
            frames_seen=5,
            last_side=None,
            counted=False,
        )
        count = count_new_tracks({2: mature_track}, min_track_frames=5)
        self.assertEqual(count, 1)
        self.assertTrue(mature_track.counted)

    def test_count_new_tracks_only_counts_once(self) -> None:
        """A track that has already been counted should not count again."""
        track = Track(
            track_id=1,
            centroid=(50, 50),
            first_centroid=(50, 50),
            previous_centroid=None,
            age=0,
            frames_seen=10,
            last_side=None,
            counted=True,
        )
        count = count_new_tracks({1: track}, min_track_frames=5)
        self.assertEqual(count, 0)

    def test_mark_all_tracks_counted_warmup(self) -> None:
        """mark_all_tracks_counted should prevent existing tracks from counting."""
        tracks = {
            1: Track(track_id=1, centroid=(50, 50), first_centroid=(50, 50),
                     previous_centroid=None, age=0, frames_seen=10,
                     last_side=None, counted=False),
            2: Track(track_id=2, centroid=(80, 80), first_centroid=(80, 80),
                     previous_centroid=None, age=0, frames_seen=10,
                     last_side=None, counted=False),
        }
        mark_all_tracks_counted(tracks)
        count = count_new_tracks(tracks, min_track_frames=5)
        self.assertEqual(count, 0)
        self.assertTrue(all(t.counted for t in tracks.values()))

    def test_event_based_runtime_counter_path_uses_gate_decisions_in_debug_artifact(self) -> None:
        self.worker.stop()
        os.environ["FC_COUNTING_MODE"] = "event_based"
        calibration_path = Path(self.temp_dir) / "factory2-runtime-calibration.json"
        calibration_path.write_text(
            '{"source_polygons":[[[0,0],[40,0],[40,100],[0,100]]],"output_polygons":[[[60,0],[100,0],[100,100],[60,100]]],"ignore_polygons":[]}',
            encoding="utf-8",
        )
        os.environ["FC_RUNTIME_CALIBRATION_PATH"] = str(calibration_path)

        with patch("app.workers.vision_worker.PersonDetector") as detector_cls:
            detector_cls.return_value = Mock()
            self.worker = VisionWorker(VideoRuntime())

        fake_counter = Mock()
        fake_counter.process_frame.return_value = RuntimeFrameResult(
            events=[CountEvent(track_id=1, count=1, reason="stable_in_output", bbox=(65.0, 20.0, 20.0, 20.0))],
            gate_decisions={
                1: GateDecision(
                    track_id=1,
                    decision="allow_source_token",
                    reason="moving_panel_candidate",
                    flags=[],
                    evidence={"source_frames": 2},
                )
            },
            tracks=[TrackDetection(track_id=1, bbox=(65.0, 20.0, 20.0, 20.0), confidence=0.9)],
        )
        self.worker._runtime_event_counter = fake_counter
        self.worker._yolo_detector.detect = Mock(
            return_value=DetectionDebugResult(
                detections=[DetectedObject(centroid=(75, 30), bbox=(65, 20, 20, 20), area=400.0)],
                foreground_mask=np.zeros((100, 100), dtype=np.uint8),
            )
        )
        self.worker._refresh_runtime_person_boxes = Mock(return_value=[(0.0, 0.0, 100.0, 100.0)])

        increment, artifact = self.worker._run_event_based_counting(np.zeros((100, 100, 3), dtype=np.uint8), None)

        self.assertEqual(increment, 1)
        fake_counter.process_frame.assert_called_once()
        self.assertEqual(fake_counter.process_frame.call_args.kwargs["person_boxes"], [(0.0, 0.0, 100.0, 100.0)])
        self.assertEqual(fake_counter.process_frame.call_args.kwargs["detections"], [{"box": (65, 20, 20, 20), "confidence": 1.0}])
        self.assertEqual(artifact["person_boxes"], [{"x": 0, "y": 0, "w": 100, "h": 100}])
        self.assertEqual(artifact["tracks"][0]["perception_gate"]["reason"], "moving_panel_candidate")

    def test_reset_counts_resets_runtime_event_counter(self) -> None:
        self.worker.stop()
        os.environ["FC_COUNTING_MODE"] = "event_based"
        calibration_path = Path(self.temp_dir) / "factory2-runtime-calibration.json"
        calibration_path.write_text(
            '{"source_polygons":[[[0,0],[40,0],[40,100],[0,100]]],"output_polygons":[[[60,0],[100,0],[100,100],[60,100]]],"ignore_polygons":[]}',
            encoding="utf-8",
        )
        os.environ["FC_RUNTIME_CALIBRATION_PATH"] = str(calibration_path)

        with patch("app.workers.vision_worker.PersonDetector") as detector_cls:
            detector_cls.return_value = Mock()
            self.worker = VisionWorker(VideoRuntime())

        fake_counter = Mock()
        self.worker._runtime_event_counter = fake_counter

        self.worker.reset_counts()

        fake_counter.reset.assert_called_once_with()
