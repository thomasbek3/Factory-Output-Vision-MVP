from __future__ import annotations

import sqlite3
import time
import unittest
import zipfile
from io import BytesIO

from tests.helpers import app_client


class DemoModeFlowTests(unittest.TestCase):
    def test_demo_mode_endpoints_and_health_writes(self) -> None:
        with app_client(demo=True) as (client, temp_dir):
            client.post(
                "/api/config/roi",
                json={"roi_polygon": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]},
            )
            client.post(
                "/api/config/line",
                json={"p1": {"x": 0.5, "y": 0.0}, "p2": {"x": 0.5, "y": 1.0}, "direction": "both"},
            )

            test_camera = client.post("/api/control/test_camera")
            self.assertEqual(test_camera.status_code, 200)
            self.assertTrue(test_camera.json()["ok"])

            restart = client.post("/api/control/restart_video")
            self.assertEqual(restart.status_code, 200)

            calibrate = client.post("/api/control/calibrate/start")
            self.assertEqual(calibrate.status_code, 200)
            self.assertEqual(calibrate.json()["state"], "CALIBRATING")

            snapshot_ok = False
            for _ in range(12):
                snap = client.get("/api/snapshot")
                if snap.status_code == 200:
                    snapshot_ok = True
                    break
                time.sleep(0.25)
            self.assertTrue(snapshot_ok)

            calibration_snapshot_ok = False
            for _ in range(12):
                snap = client.get("/api/snapshot?overlay_mode=calibration")
                if snap.status_code == 200:
                    calibration_snapshot_ok = True
                    break
                time.sleep(0.25)
            self.assertTrue(calibration_snapshot_ok)

            debug_snapshot_ok = False
            for _ in range(12):
                debug_snapshot = client.get("/api/diagnostics/snapshot/debug?view=tracks")
                if debug_snapshot.status_code == 200:
                    debug_snapshot_ok = True
                    break
                time.sleep(0.25)
            self.assertTrue(debug_snapshot_ok)

            diagnostics = client.get("/api/diagnostics/sysinfo")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertEqual(diagnostics.json()["source_kind"], "demo")

            bundle = client.get("/api/diagnostics/support_bundle.zip")
            self.assertEqual(bundle.status_code, 200)
            names = zipfile.ZipFile(BytesIO(bundle.content)).namelist()
            self.assertIn("factory_counter.db", names)
            self.assertIn("config_snapshot.json", names)
            self.assertIn("diagnostics.json", names)

            time.sleep(0.3)
            conn = sqlite3.connect(f"{temp_dir}/test.db")
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0], 1)
