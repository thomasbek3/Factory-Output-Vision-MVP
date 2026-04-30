from __future__ import annotations

import unittest

from tests.helpers import app_client


class ApiSmokeTests(unittest.TestCase):
    def test_unconfigured_core_api_contracts(self) -> None:
        with app_client() as (client, _temp_dir):
            status = client.get("/api/status")
            self.assertEqual(status.status_code, 200)
            status_payload = status.json()
            self.assertIn("count_source", status_payload)
            self.assertIn("operator_absent", status_payload)
            self.assertIn("calibration_progress_pct", status_payload)
            self.assertIn("calibration_elapsed_sec", status_payload)
            self.assertIn("calibration_target_duration_sec", status_payload)
            self.assertIn("runtime_total", status_payload)
            self.assertIn("proof_backed_total", status_payload)
            self.assertIn("runtime_inferred_only", status_payload)
            self.assertEqual(status_payload["count_source"], "vision")
            self.assertEqual(status_payload["runtime_total"], 0)
            self.assertEqual(status_payload["proof_backed_total"], 0)
            self.assertEqual(status_payload["runtime_inferred_only"], 0)

            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            config_payload = config.json()
            self.assertIn("baseline_rate_per_min", config_payload)
            self.assertIsNone(config_payload["camera_password"])

            events = client.get("/api/events")
            self.assertEqual(events.status_code, 200)
            self.assertEqual(events.json()["items"], [])

            diagnostics = client.get("/api/diagnostics/sysinfo")
            self.assertEqual(diagnostics.status_code, 200)
            diagnostics_payload = diagnostics.json()
            self.assertEqual(diagnostics_payload["current_state"], "NOT_CONFIGURED")
            self.assertIn("db_path", diagnostics_payload)
            self.assertIn("log_directory", diagnostics_payload)
            self.assertIn("reader_last_sequence_index", diagnostics_payload)
            self.assertIn("reader_last_source_timestamp_sec", diagnostics_payload)
            self.assertIn("recent_count_events", diagnostics_payload)
            self.assertEqual(diagnostics_payload["recent_count_events"], [])

            restart = client.post("/api/control/restart_video")
            self.assertEqual(restart.status_code, 503)

    def test_invalid_roi_rejected(self) -> None:
        with app_client() as (client, _temp_dir):
            response = client.post(
                "/api/config/roi",
                json={"roi_polygon": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}]},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("at least 3 points", response.json()["detail"])

    def test_semantic_line_direction_is_accepted(self) -> None:
        with app_client() as (client, _temp_dir):
            response = client.post(
                "/api/config/line",
                json={"p1": {"x": 0.2, "y": 0.2}, "p2": {"x": 0.8, "y": 0.2}, "direction": "right_to_left"},
            )
            self.assertEqual(response.status_code, 200)

            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            self.assertEqual(config.json()["line"]["direction"], "right_to_left")

    def test_manual_count_adjust(self) -> None:
        with app_client() as (client, _temp_dir):
            response = client.post("/api/control/adjust_count", json={"delta": 5})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["counts_this_minute"], 5)
            self.assertEqual(payload["counts_this_hour"], 5)
            self.assertEqual(payload["runtime_total"], 5)
            self.assertEqual(payload["proof_backed_total"], 0)
            self.assertEqual(payload["runtime_inferred_only"], 0)

            response = client.post("/api/control/adjust_count", json={"delta": -2})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["counts_this_hour"], 3)
            self.assertEqual(payload["runtime_total"], 3)
            self.assertEqual(payload["proof_backed_total"], 0)
            self.assertEqual(payload["runtime_inferred_only"], 0)

    def test_configured_without_line_in_demo_mode(self) -> None:
        with app_client(demo=True) as (client, _temp_dir):
            client.post(
                "/api/config/roi",
                json={
                    "roi_polygon": [
                        {"x": 0.1, "y": 0.1},
                        {"x": 0.9, "y": 0.1},
                        {"x": 0.9, "y": 0.9},
                        {"x": 0.1, "y": 0.9},
                    ]
                },
            )
            # start_monitoring calls _is_configured() which reads from DB
            monitor = client.post("/api/control/monitor/start")
            self.assertEqual(monitor.status_code, 200)
            # System should be configured with just ROI (no line required)
            self.assertNotEqual(monitor.json()["state"], "NOT_CONFIGURED")

    def test_live_stream_contract_in_demo_mode(self) -> None:
        with app_client(demo=True) as (client, _temp_dir):
            response = client.get("/api/stream.mjpg?frame_limit=1")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers["content-type"].startswith("multipart/x-mixed-replace"))
            self.assertIn(b"--frame", response.content)
            self.assertIn(b"Content-Type: image/jpeg", response.content)
