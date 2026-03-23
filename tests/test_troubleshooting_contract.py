from __future__ import annotations

from pathlib import Path
import time
import unittest

from tests.helpers import app_client


class TroubleshootingContractTests(unittest.TestCase):
    def test_troubleshooting_routes_and_actions(self) -> None:
        with app_client(demo=True) as (client, _temp_dir):
            client.post(
                "/api/config/roi",
                json={"roi_polygon": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]},
            )
            client.post(
                "/api/config/line",
                json={"p1": {"x": 0.5, "y": 0.0}, "p2": {"x": 0.5, "y": 1.0}, "direction": "both"},
            )

            diagnostics = client.get("/api/diagnostics/sysinfo")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertIn("current_state", diagnostics.json())
            self.assertIn("reader_alive", diagnostics.json())
            self.assertIn("demo_playback_speed", diagnostics.json())
            self.assertIn("demo_video_name", diagnostics.json())
            self.assertIn("person_ignore_enabled", diagnostics.json())
            self.assertIn("people_detected_count", diagnostics.json())

            list_before = client.get("/api/control/demo/videos")
            self.assertEqual(list_before.status_code, 200)
            self.assertIsInstance(list_before.json()["items"], list)

            with Path("demo/demo.mp4").open("rb") as source_file:
                upload = client.post(
                    "/api/control/demo/videos/upload",
                    files={"file": ("uploaded_demo.MOV", source_file, "video/quicktime")},
                )
            self.assertEqual(upload.status_code, 200)

            list_after = client.get("/api/control/demo/videos")
            self.assertEqual(list_after.status_code, 200)
            uploaded_item = next(item for item in list_after.json()["items"] if item["name"] == "uploaded_demo.mp4")
            self.assertTrue(uploaded_item["selected"])

            active_demo_content = client.get("/api/control/demo/videos/active/content")
            self.assertEqual(active_demo_content.status_code, 200)
            self.assertEqual(active_demo_content.headers["content-type"], "video/mp4")
            self.assertGreater(len(active_demo_content.content), 0)

            reselect = client.post("/api/control/demo/videos/select", json={"path": uploaded_item["path"]})
            self.assertEqual(reselect.status_code, 200)

            active_video = client.get("/api/control/demo/videos/active/content")
            self.assertEqual(active_video.status_code, 200)
            self.assertTrue(active_video.headers["content-type"].startswith("video/"))

            reset_calibration = client.post("/api/control/reset_calibration")
            self.assertEqual(reset_calibration.status_code, 200)

            restart_video = client.post("/api/control/restart_video")
            self.assertEqual(restart_video.status_code, 200)

            set_speed = client.post("/api/control/demo/playback_speed", json={"speed_multiplier": 2.0})
            self.assertEqual(set_speed.status_code, 200)

            toggle_person_ignore = client.post("/api/control/person_ignore", json={"enabled": True})
            self.assertEqual(toggle_person_ignore.status_code, 200)

            counts_reset = client.post("/api/control/reset_counts")
            self.assertEqual(counts_reset.status_code, 200)
            self.assertEqual(counts_reset.json()["counts_this_minute"], 0)
            self.assertEqual(counts_reset.json()["counts_this_hour"], 0)

            toggle_person_ignore_off = client.post("/api/control/person_ignore", json={"enabled": False})
            self.assertEqual(toggle_person_ignore_off.status_code, 200)

            start_monitor = client.post("/api/control/monitor/start")
            self.assertEqual(start_monitor.status_code, 200)

            debug_mask_ok = False
            for _ in range(12):
                debug_mask = client.get("/api/diagnostics/snapshot/debug?view=mask")
                if debug_mask.status_code == 200:
                    debug_mask_ok = True
                    break
                time.sleep(0.25)
            self.assertTrue(debug_mask_ok)

            debug_tracks = client.get("/api/diagnostics/snapshot/debug?view=tracks")
            self.assertEqual(debug_tracks.status_code, 200)

            debug_people = client.get("/api/diagnostics/snapshot/debug?view=people")
            self.assertEqual(debug_people.status_code, 200)

            events = client.get("/api/events?limit=12")
            self.assertEqual(events.status_code, 200)
            self.assertIsInstance(events.json()["items"], list)

            status = client.get("/api/status")
            self.assertEqual(status.status_code, 200)
            self.assertIn("last_frame_age_sec", status.json())

            diagnostics_after = client.get("/api/diagnostics/sysinfo")
            self.assertEqual(diagnostics_after.status_code, 200)
            self.assertEqual(diagnostics_after.json()["demo_playback_speed"], 2.0)
            self.assertFalse(diagnostics_after.json()["person_ignore_enabled"])
            self.assertEqual(diagnostics_after.json()["demo_video_name"], "uploaded_demo.mp4")

            bundle = client.get("/api/diagnostics/support_bundle.zip")
            self.assertEqual(bundle.status_code, 200)
            self.assertEqual(bundle.headers["content-type"], "application/zip")
