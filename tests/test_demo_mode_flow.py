from __future__ import annotations

import sqlite3
import shutil
import tempfile
import time
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from tests.helpers import app_client


class DemoModeFlowTests(unittest.TestCase):
    def test_deterministic_demo_runner_reveals_cached_receipts_over_api(self) -> None:
        temp_dir = tempfile.mkdtemp(prefix="factory_counter_deterministic_demo_")
        try:
            calibration_path = Path(temp_dir) / "factory2-runtime-calibration.json"
            calibration_path.write_text(
                '{"source_polygons":[[[0,0],[40,0],[40,100],[0,100]]],"output_polygons":[[[60,0],[100,0],[100,100],[60,100]]],"ignore_polygons":[]}',
                encoding="utf-8",
            )
            report_path = Path(temp_dir) / "demo_runtime_event_audit.json"
            report_path.write_text(
                f"""{{
  "schema_version": "factory2-runtime-event-audit-v1",
  "video_path": "{Path('demo/demo.mp4').resolve()}",
  "calibration_path": "{calibration_path.resolve()}",
  "model_path": "{Path('models/panel_in_transit.pt').resolve()}",
  "start_seconds": 0.0,
  "end_seconds": null,
  "processing_fps": 10.0,
  "video_fps": 30.0,
  "sampled_frame_count": 10,
  "final_count": 2,
  "elapsed_sec": 0.5,
  "events": [
    {{
      "event_ts": 0.0,
      "track_id": 1,
      "reason": "source_token_accepted",
      "count_total": 1,
      "bbox": [1.0, 2.0, 3.0, 4.0],
      "source_track_id": 10,
      "source_token_id": "token-1",
      "chain_id": "chain-1",
      "source_bbox": [0.0, 1.0, 2.0, 3.0],
      "provenance_status": "source_token_authorized",
      "count_authority": "source_token_authorized",
      "predecessor_chain_track_ids": [10],
      "source_observation_count": 2,
      "output_observation_count": 2,
      "gate_decision": null
    }},
    {{
      "event_ts": 0.2,
      "track_id": 2,
      "reason": "approved_delivery_chain",
      "count_total": 2,
      "bbox": [5.0, 6.0, 7.0, 8.0],
      "source_track_id": null,
      "source_token_id": null,
      "chain_id": "chain-2",
      "source_bbox": null,
      "provenance_status": "synthetic_approved_chain_token",
      "count_authority": "runtime_inferred_only",
      "predecessor_chain_track_ids": [20],
      "source_observation_count": 0,
      "output_observation_count": 3,
      "gate_decision": null
    }}
  ],
  "track_histories": {{}}
}}
""",
                encoding="utf-8",
            )

            with app_client(
                demo=True,
                extra_env={
                    "FC_COUNTING_MODE": "event_based",
                    "FC_PERSON_DETECT_ENABLED": "0",
                    "FC_RUNTIME_CALIBRATION_PATH": str(calibration_path),
                    "FC_DEMO_COUNT_MODE": "deterministic_file_runner",
                    "FC_DEMO_COUNT_CACHE_PATH": str(report_path),
                },
            ) as (client, _ignored_temp_dir):
                response = client.post("/api/control/monitor/start")
                self.assertEqual(response.status_code, 200)

                final_status = None
                for _ in range(16):
                    final_status = client.get("/api/status").json()
                    if final_status["runtime_total"] >= 2:
                        break
                    time.sleep(0.25)

                assert final_status is not None
                self.assertEqual(final_status["runtime_total"], 2)
                self.assertEqual(final_status["proof_backed_total"], 1)
                self.assertEqual(final_status["runtime_inferred_only"], 1)
                self.assertGreater(final_status["demo_elapsed_sec"], 0.0)
                self.assertTrue(final_status["demo_playback_active"])

                diagnostics = client.get("/api/diagnostics/sysinfo")
                self.assertEqual(diagnostics.status_code, 200)
                self.assertEqual(diagnostics.json()["demo_count_mode"], "deterministic_file_runner")
                self.assertEqual(diagnostics.json()["demo_receipt_total"], 2)
                self.assertEqual(diagnostics.json()["demo_revealed_receipts"], 2)
                self.assertGreater(diagnostics.json()["demo_elapsed_sec"], 0.0)
                self.assertTrue(diagnostics.json()["demo_playback_active"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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
