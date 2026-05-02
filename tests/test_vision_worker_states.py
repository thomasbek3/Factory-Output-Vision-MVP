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
from app.services.counting import DetectedObject, DetectionDebugResult, Track, count_dead_tracks, count_new_tracks, mark_all_tracks_counted
from app.services.frame_reader import ReaderSnapshot
from app.services.perception_gate import GateDecision
from app.services.runtime_event_counter import RuntimeFrameResult
from app.services.video_runtime import VideoRuntime
from app.services.video_source import SourceSelection
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
            "FC_DEMO_COUNT_MODE": os.environ.get("FC_DEMO_COUNT_MODE"),
            "FC_PERSON_DETECT_ENABLED": os.environ.get("FC_PERSON_DETECT_ENABLED"),
            "FC_PERSON_DETECT_FPS": os.environ.get("FC_PERSON_DETECT_FPS"),
            "FC_COUNTING_MODE": os.environ.get("FC_COUNTING_MODE"),
            "FC_RUNTIME_CALIBRATION_PATH": os.environ.get("FC_RUNTIME_CALIBRATION_PATH"),
            "FC_EVENT_DETECTION_CLUSTER_DISTANCE": os.environ.get("FC_EVENT_DETECTION_CLUSTER_DISTANCE"),
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

    def test_start_monitoring_restarts_demo_source_and_clears_pending_frames(self) -> None:
        restart_calls: list[str] = []
        discard_calls: list[str] = []

        def fake_restart() -> None:
            restart_calls.append("restart")

        def fake_discard() -> None:
            discard_calls.append("discard")

        self.worker.video_runtime.restart = fake_restart  # type: ignore[method-assign]
        self.worker.video_runtime.reader.discard_pending_frames = fake_discard  # type: ignore[method-assign]

        status = self.worker.start_monitoring()

        self.assertEqual(restart_calls, ["restart"])
        self.assertEqual(discard_calls, ["discard"])
        self.assertEqual(status["state"], "IDLE")

    def test_demo_reader_frame_selection_uses_synchronous_pump_when_available(self) -> None:
        expected = ReaderSnapshot(
            frame=np.zeros((2, 2, 3), dtype=np.uint8),
            last_frame_time=1.0,
            source="demo",
            sequence_index=7,
        )
        fake_reader = Mock()
        fake_reader.is_synchronous_demo_mode.return_value = True
        fake_reader.pump_next_demo_frame.return_value = expected
        fake_reader.consume_next_frame.return_value = None
        self.worker.video_runtime.reader = fake_reader  # type: ignore[assignment]

        snapshot = self.worker._next_reader_frame(source_is_demo=True)

        self.assertIs(snapshot, expected)
        fake_reader.pump_next_demo_frame.assert_called_once_with()
        fake_reader.consume_next_frame.assert_not_called()

    def test_synchronous_demo_pacing_uses_source_clock(self) -> None:
        fake_reader = Mock()
        fake_reader.is_synchronous_demo_mode.return_value = True
        self.worker.video_runtime.reader = fake_reader  # type: ignore[assignment]
        self.worker.video_runtime.current_demo_playback_speed = Mock(return_value=1.0)  # type: ignore[method-assign]
        self.worker._demo_live_started_at_ts = 100.0
        snapshot = ReaderSnapshot(
            frame=np.zeros((2, 2, 3), dtype=np.uint8),
            last_frame_time=101.0,
            source="demo",
            source_timestamp_sec=1.0,
        )

        with patch("app.workers.vision_worker.time.time", return_value=100.96):
            delay = self.worker._next_frame_pacing_delay(
                default_delay=0.1,
                loop_started_ts=100.0,
                source_is_demo=True,
                frame_snapshot=snapshot,
            )

        self.assertEqual(delay, 0.0)

        with patch("app.workers.vision_worker.time.time", return_value=100.50):
            source_clock_delay = self.worker._next_frame_pacing_delay(
                default_delay=0.1,
                loop_started_ts=100.0,
                source_is_demo=True,
                frame_snapshot=snapshot,
            )

        self.assertEqual(source_clock_delay, 0.0)

        with patch("app.workers.vision_worker.time.time", return_value=101.20):
            catchup_delay = self.worker._next_frame_pacing_delay(
                default_delay=0.1,
                loop_started_ts=101.2,
                source_is_demo=True,
                frame_snapshot=snapshot,
            )

        self.assertEqual(catchup_delay, 0.0)

    def test_synchronous_demo_pending_frames_do_not_bypass_source_clock_pacing(self) -> None:
        fake_reader = Mock()
        fake_reader.is_synchronous_demo_mode.return_value = True
        self.worker.video_runtime.reader = fake_reader  # type: ignore[assignment]

        self.assertFalse(self.worker._should_drain_pending_frames_without_delay(source_is_demo=True, pending_frames=3))

        fake_reader.is_synchronous_demo_mode.return_value = False
        self.assertTrue(self.worker._should_drain_pending_frames_without_delay(source_is_demo=True, pending_frames=3))
        self.assertTrue(self.worker._should_drain_pending_frames_without_delay(source_is_demo=False, pending_frames=3))
        self.assertFalse(self.worker._should_drain_pending_frames_without_delay(source_is_demo=False, pending_frames=0))

    def test_idle_synchronous_demo_reader_does_not_trigger_stall_recovery(self) -> None:
        fake_reader = Mock()
        fake_reader.is_synchronous_demo_mode.return_value = True
        self.worker.video_runtime.reader = fake_reader  # type: ignore[assignment]
        self.worker.monitoring_enabled = False
        self.worker.calibrating = False

        should_handle = self.worker._should_handle_video_stall(
            source_is_demo=True,
            reader_status={"demo_finished": False},
        )

        self.assertFalse(should_handle)

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

    def test_count_dead_tracks_can_require_travel(self) -> None:
        """Event-based tracks can filter stationary detection flicker."""
        stationary_track = Track(
            track_id=1,
            centroid=(104, 100),
            first_centroid=(100, 100),
            previous_centroid=(103, 100),
            age=10,
            frames_seen=20,
            last_side=None,
            counted=False,
        )
        moving_track = Track(
            track_id=2,
            centroid=(260, 100),
            first_centroid=(100, 100),
            previous_centroid=(240, 100),
            age=10,
            frames_seen=20,
            last_side=None,
            counted=False,
        )

        count = count_dead_tracks([stationary_track, moving_track], min_track_frames=5, min_travel_px=75)
        self.assertEqual(count, 1)

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
            events=[
                CountEvent(
                    track_id=1,
                    count=1,
                    reason="approved_delivery_chain",
                    bbox=(65.0, 20.0, 20.0, 20.0),
                    provenance_status="synthetic_approved_chain_token",
                    count_authority="runtime_inferred_only",
                )
            ],
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
        self.assertEqual(artifact["event_count_authorities"], ["runtime_inferred_only"])
        self.assertEqual(artifact["count_events"][0]["chain_id"], None)
        self.assertEqual(artifact["count_events"][0]["provenance_status"], "synthetic_approved_chain_token")
        self.assertEqual(artifact["tracks"][0]["perception_gate"]["reason"], "moving_panel_candidate")

    def test_event_based_dead_track_path_emits_count_event_payload(self) -> None:
        self.worker._runtime_event_counter = None
        dead_track = Track(
            track_id=7,
            centroid=(75, 80),
            first_centroid=(50, 60),
            previous_centroid=(70, 78),
            age=0,
            frames_seen=8,
            last_side=None,
            counted=False,
        )
        fake_tracker = Mock()
        fake_tracker.update_with_dead.return_value = ([dead_track], {})
        self.worker._event_tracker = fake_tracker
        self.worker._counting_mode = "event_based"
        self.worker._yolo_detector.detect = Mock(
            return_value=DetectionDebugResult(
                detections=[],
                foreground_mask=np.zeros((100, 100), dtype=np.uint8),
            )
        )

        increment, artifact = self.worker._run_event_based_counting(np.zeros((100, 100, 3), dtype=np.uint8), None)

        self.assertEqual(increment, 1)
        self.assertEqual(artifact["count_events"][0]["track_id"], 7)
        self.assertEqual(artifact["count_events"][0]["reason"], "dead_track_event")
        self.assertEqual(artifact["count_events"][0]["centroid"], [75, 80])
        self.assertEqual(artifact["count_events"][0]["count_authority"], "runtime_inferred_only")

    def test_event_based_dead_track_path_clusters_nearby_same_frame_detections(self) -> None:
        os.environ["FC_EVENT_DETECTION_CLUSTER_DISTANCE"] = "30"
        fake_tracker = Mock()
        fake_tracker.update_with_dead.return_value = ([], {})
        self.worker._event_tracker = fake_tracker
        self.worker._runtime_event_counter = None
        self.worker._counting_mode = "event_based"
        self.worker._yolo_detector.detect = Mock(
            return_value=DetectionDebugResult(
                detections=[
                    DetectedObject(centroid=(10, 10), bbox=(0, 0, 20, 20), area=400.0),
                    DetectedObject(centroid=(25, 10), bbox=(15, 0, 20, 20), area=400.0),
                    DetectedObject(centroid=(100, 100), bbox=(90, 90, 20, 20), area=400.0),
                ],
                foreground_mask=np.zeros((120, 120), dtype=np.uint8),
            )
        )

        _, artifact = self.worker._run_event_based_counting(np.zeros((120, 120, 3), dtype=np.uint8), None)

        fake_tracker.update_with_dead.assert_called_once_with([(18, 10), (100, 100)])
        self.assertEqual(artifact["clustered_centroids"], [(18, 10), (100, 100)])

    def test_diagnostics_include_recent_runtime_count_trace(self) -> None:
        self.worker.state = "RUNNING_GREEN"
        self.worker._record_count_events(
            [
                {
                    "event_ts": 305.708,
                    "track_id": 108,
                    "count": 1,
                    "reason": "approved_delivery_chain",
                    "bbox": [65.0, 20.0, 20.0, 20.0],
                    "source_track_id": 107,
                    "source_token_id": None,
                    "chain_id": "proof-source-track:107",
                    "source_bbox": None,
                    "provenance_status": "synthetic_approved_chain_token",
                    "count_authority": "runtime_inferred_only",
                    "track_zone": "output",
                    "person_overlap_ratio": 0.0,
                    "outside_person_ratio": 1.0,
                    "predecessor_chain_track_ids": [104, 105, 106],
                }
            ],
            reader_sequence_index=4207,
            reader_frame_time=123.456789,
            source_timestamp_sec=305.708,
            source_kind="demo",
        )

        diagnostics = self.worker.get_diagnostics(
            uptime_sec=12.3,
            db_path=os.path.join(self.temp_dir, "worker.db"),
            log_directory=os.path.join(self.temp_dir, "logs"),
        )

        self.assertEqual(diagnostics["recent_count_events"][0]["track_id"], 108)
        self.assertEqual(diagnostics["recent_count_events"][0]["count_authority"], "runtime_inferred_only")
        self.assertEqual(diagnostics["recent_count_events"][0]["reader_frame_sequence_index"], 4207)
        self.assertEqual(diagnostics["recent_count_events"][0]["event_ts"], 305.708)
        self.assertEqual(diagnostics["recent_count_events"][0]["runtime_total_after_event"], 1)
        self.assertEqual(diagnostics["recent_count_events"][0]["runtime_inferred_only_after_event"], 1)
        self.assertEqual(diagnostics["recent_count_events"][0]["worker_state"], "RUNNING_GREEN")

    def test_demo_eof_flush_records_runtime_events_once(self) -> None:
        self.worker.state = "RUNNING_GREEN"
        fake_counter = Mock()
        fake_counter.flush_end_of_stream.return_value = RuntimeFrameResult(
            events=[
                CountEvent(
                    track_id=152,
                    count=1,
                    reason="approved_delivery_chain",
                    bbox=(627.0, 533.0, 265.0, 34.0),
                    source_track_id=145,
                    provenance_status="synthetic_approved_chain_token",
                    count_authority="runtime_inferred_only",
                )
            ],
            gate_decisions={},
            tracks=[],
        )
        self.worker._runtime_event_counter = fake_counter

        flushed = self.worker._flush_demo_end_of_stream_events(
            reader_sequence_index=4250,
            reader_frame_time=123.45,
        )
        flushed_again = self.worker._flush_demo_end_of_stream_events(
            reader_sequence_index=4250,
            reader_frame_time=123.45,
        )

        self.assertEqual(flushed, 1)
        self.assertEqual(flushed_again, 0)
        self.assertEqual(self.worker.get_status()["runtime_total"], 1)
        self.assertEqual(self.worker.get_status()["runtime_inferred_only"], 1)
        fake_counter.flush_end_of_stream.assert_called_once_with(iterations=2)

    def test_demo_eof_flush_counts_active_event_tracker_tracks_once(self) -> None:
        self.worker.state = "RUNNING_GREEN"
        self.worker._runtime_event_counter = None
        self.worker._event_tracker = Mock()
        self.worker._event_tracker.tracks = {
            11: Track(
                track_id=11,
                centroid=(80, 90),
                first_centroid=(70, 85),
                previous_centroid=(78, 89),
                age=0,
                frames_seen=8,
                last_side=None,
                counted=False,
            ),
            12: Track(
                track_id=12,
                centroid=(20, 25),
                first_centroid=(20, 25),
                previous_centroid=None,
                age=0,
                frames_seen=2,
                last_side=None,
                counted=False,
            ),
        }

        flushed = self.worker._flush_demo_end_of_stream_events(
            reader_sequence_index=9460,
            reader_frame_time=123.45,
            reader_source_timestamp_sec=946.5,
        )
        flushed_again = self.worker._flush_demo_end_of_stream_events(
            reader_sequence_index=9460,
            reader_frame_time=123.45,
            reader_source_timestamp_sec=946.5,
        )

        self.assertEqual(flushed, 1)
        self.assertEqual(flushed_again, 0)
        self.assertEqual(self.worker.get_status()["runtime_total"], 1)
        self.assertEqual(self.worker.get_status()["runtime_inferred_only"], 1)
        diagnostics = self.worker.get_diagnostics(
            uptime_sec=12.3,
            db_path=os.path.join(self.temp_dir, "worker.db"),
            log_directory=os.path.join(self.temp_dir, "logs"),
        )
        self.assertEqual(diagnostics["recent_count_events"][0]["reason"], "end_of_stream_active_track_event")
        self.assertEqual(diagnostics["recent_count_events"][0]["event_ts"], 946.5)

    def test_runtime_person_boxes_reuse_cached_detections_within_detect_interval(self) -> None:
        self.worker.stop()
        os.environ["FC_COUNTING_MODE"] = "event_based"
        os.environ["FC_PERSON_DETECT_ENABLED"] = "1"
        os.environ["FC_PERSON_DETECT_FPS"] = "2"
        calibration_path = Path(self.temp_dir) / "factory2-runtime-calibration.json"
        calibration_path.write_text(
            '{"source_polygons":[[[0,0],[40,0],[40,100],[0,100]]],"output_polygons":[[[60,0],[100,0],[100,100],[60,100]]],"ignore_polygons":[]}',
            encoding="utf-8",
        )
        os.environ["FC_RUNTIME_CALIBRATION_PATH"] = str(calibration_path)

        first_detection = Mock(x=1, y=2, w=3, h=4, confidence=0.9)
        second_detection = Mock(x=10, y=20, w=30, h=40, confidence=0.8)
        detector = Mock()
        detector.detect_people.side_effect = [[first_detection], [second_detection]]

        with patch("app.workers.vision_worker.PersonDetector", return_value=detector):
            self.worker = VisionWorker(VideoRuntime())

        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        with patch("app.workers.vision_worker.time.time", side_effect=[100.0, 100.2, 100.8]):
            first_boxes = self.worker._refresh_runtime_person_boxes(frame)
            second_boxes = self.worker._refresh_runtime_person_boxes(frame)
            third_boxes = self.worker._refresh_runtime_person_boxes(frame)

        self.assertEqual(detector.detect_people.call_count, 2)
        self.assertEqual(first_boxes, [(1.0, 2.0, 3.0, 4.0)])
        self.assertEqual(second_boxes, [(1.0, 2.0, 3.0, 4.0)])
        self.assertEqual(third_boxes, [(10.0, 20.0, 30.0, 40.0)])

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
        self.worker._proof_backed_total = 4
        self.worker._runtime_inferred_only_total = 2

        self.worker.reset_counts()

        fake_counter.reset.assert_called_once_with()
        self.assertEqual(self.worker.get_status()["proof_backed_total"], 0)
        self.assertEqual(self.worker.get_status()["runtime_inferred_only"], 0)

    def test_demo_playback_completion_freezes_counts_without_reconnect(self) -> None:
        self.worker.monitoring_enabled = True
        self.worker.state = "RUNNING_GREEN"
        self.worker.counter_state.counts_this_hour = 23
        self.worker.counter_state.counts_this_minute = 1
        self.worker._runtime_total = 23
        self.worker._proof_backed_total = 21
        self.worker._runtime_inferred_only_total = 2

        self.worker._handle_demo_playback_complete()

        status = self.worker.get_status()
        self.assertEqual(status["state"], "DEMO_COMPLETE")
        self.assertFalse(self.worker.monitoring_enabled)
        self.assertFalse(self.worker.calibrating)
        self.assertEqual(status["runtime_total"], 23)
        self.assertEqual(status["proof_backed_total"], 21)
        self.assertEqual(status["runtime_inferred_only"], 2)

    def test_demo_completion_waits_for_pending_frame_queue_to_drain(self) -> None:
        self.assertFalse(
            self.worker._should_finalize_demo_playback(
                source_is_demo=True,
                reader_status={"demo_finished": True, "pending_frames": 2},
                deterministic_demo=False,
            )
        )
        self.assertTrue(
            self.worker._should_finalize_demo_playback(
                source_is_demo=True,
                reader_status={"demo_finished": True, "pending_frames": 0},
                deterministic_demo=False,
            )
        )

    def test_demo_eof_is_not_treated_as_video_stall_while_queue_drains(self) -> None:
        self.assertFalse(
            self.worker._should_handle_video_stall(
                source_is_demo=True,
                reader_status={"demo_finished": True, "pending_frames": 2},
            )
        )
        self.assertTrue(
            self.worker._should_handle_video_stall(
                source_is_demo=False,
                reader_status={"demo_finished": False, "pending_frames": 0},
            )
        )

    def test_deterministic_demo_start_monitoring_restarts_preview_and_arms_runner(self) -> None:
        self.worker.stop()
        os.environ["FC_COUNTING_MODE"] = "event_based"
        calibration_path = Path(self.temp_dir) / "factory2-runtime-calibration.json"
        calibration_path.write_text(
            '{"source_polygons":[[[0,0],[40,0],[40,100],[0,100]]],"output_polygons":[[[60,0],[100,0],[100,100],[60,100]]],"ignore_polygons":[]}',
            encoding="utf-8",
        )
        os.environ["FC_RUNTIME_CALIBRATION_PATH"] = str(calibration_path)
        os.environ["FC_DEMO_COUNT_MODE"] = "deterministic_file_runner"

        with patch("app.workers.vision_worker.PersonDetector") as detector_cls:
            detector_cls.return_value = Mock()
            self.worker = VisionWorker(VideoRuntime())

        fake_runner = Mock()
        fake_runner.current_elapsed_sec.return_value = 0.0
        self.worker._deterministic_demo_runner = fake_runner
        self.worker.video_runtime.current_source_kind = Mock(return_value="demo")  # type: ignore[method-assign]
        self.worker.video_runtime.current_source_selection = Mock(  # type: ignore[method-assign]
            return_value=SourceSelection(is_demo=True, source="/tmp/factory2.MOV", candidates=("/tmp/factory2.MOV",))
        )
        self.worker.video_runtime.current_demo_playback_speed = Mock(return_value=8.0)  # type: ignore[method-assign]
        self.worker.video_runtime.restart = Mock()  # type: ignore[method-assign]
        self.worker.counter_state.counts_this_hour = 9
        self.worker._proof_backed_total = 7
        self.worker._runtime_inferred_only_total = 2

        status = self.worker.start_monitoring()

        self.worker.video_runtime.restart.assert_called_once_with()
        fake_runner.prepare.assert_called_once()
        fake_runner.arm.assert_called_once_with(playback_speed=8.0)
        self.assertEqual(status["state"], "IDLE")
        self.assertTrue(self.worker.monitoring_enabled)
        self.assertEqual(status["runtime_total"], 0)
        self.assertEqual(status["proof_backed_total"], 0)
        self.assertEqual(status["runtime_inferred_only"], 0)

    def test_deterministic_demo_counting_reveals_due_receipts(self) -> None:
        fake_runner = Mock()
        fake_runner.armed = True
        fake_runner.active = False
        fake_runner.drain_due_events.return_value = [
            {"track_id": 11, "count_authority": "source_token_authorized"},
            {"track_id": 12, "count_authority": "runtime_inferred_only"},
        ]
        self.worker._deterministic_demo_runner = fake_runner

        increment, artifact = self.worker._run_deterministic_demo_counting(np.zeros((32, 32, 3), dtype=np.uint8))

        fake_runner.activate.assert_called_once()
        fake_runner.drain_due_events.assert_called_once()
        self.assertEqual(increment, 2)
        self.assertEqual(artifact["event_count_authorities"], ["source_token_authorized", "runtime_inferred_only"])
