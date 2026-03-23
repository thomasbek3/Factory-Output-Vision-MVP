from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from collections import deque

from app.db.config_repo import update_roi_polygon
from app.db.database import init_db
from app.services.counting import Track, count_new_tracks, mark_all_tracks_counted
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
