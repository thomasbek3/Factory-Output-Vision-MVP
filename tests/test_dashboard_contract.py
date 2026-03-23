from __future__ import annotations

import time
import unittest

from tests.helpers import app_client


class DashboardContractTests(unittest.TestCase):
    def test_dashboard_metrics_socket_and_controls(self) -> None:
        with app_client(demo=True) as (client, _temp_dir):
            client.post(
                "/api/config/roi",
                json={"roi_polygon": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]},
            )
            client.post(
                "/api/config/line",
                json={"p1": {"x": 0.5, "y": 0.0}, "p2": {"x": 0.5, "y": 1.0}, "direction": "both"},
            )

            with client.websocket_connect("/ws/metrics") as websocket:
                payload = websocket.receive_json()
                self.assertIn("state", payload)
                self.assertIn("counts_this_minute", payload)
                self.assertIn("rolling_rate_per_min", payload)
                self.assertEqual(payload["count_source"], "vision")

            start_monitor = client.post("/api/control/monitor/start")
            self.assertEqual(start_monitor.status_code, 200)

            recalibrate = client.post("/api/control/reset_calibration")
            self.assertEqual(recalibrate.status_code, 200)

            start_calibration = client.post("/api/control/calibrate/start")
            self.assertEqual(start_calibration.status_code, 200)
            self.assertEqual(start_calibration.json()["state"], "CALIBRATING")

            events = client.get("/api/events?limit=20")
            self.assertEqual(events.status_code, 200)
            self.assertGreaterEqual(len(events.json()["items"]), 1)

            snapshot_ok = False
            for _ in range(12):
                snapshot = client.get("/api/snapshot")
                if snapshot.status_code == 200:
                    snapshot_ok = True
                    break
                time.sleep(0.25)
            self.assertTrue(snapshot_ok)
