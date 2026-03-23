from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.helpers import app_client


class ReactCutoverTests(unittest.TestCase):
    def test_routes_return_clear_message_when_frontend_build_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="factory_counter_no_dist_") as frontend_dist:
            with app_client(extra_env={"FC_FRONTEND_DIST": frontend_dist}) as (client, _temp_dir):
                root = client.get("/")
                self.assertEqual(root.status_code, 503)
                self.assertIn("Frontend build not available", root.text)

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 503)
                self.assertIn("Frontend build not available", dashboard.text)

                wizard = client.get("/wizard/welcome", follow_redirects=False)
                self.assertEqual(wizard.status_code, 307)
                self.assertEqual(wizard.headers["location"], "/wizard")

                legacy_dashboard = client.get("/legacy/dashboard", follow_redirects=False)
                self.assertEqual(legacy_dashboard.status_code, 307)
                self.assertEqual(legacy_dashboard.headers["location"], "/dashboard")

                legacy_wizard = client.get("/legacy/wizard/welcome", follow_redirects=False)
                self.assertEqual(legacy_wizard.status_code, 307)
                self.assertEqual(legacy_wizard.headers["location"], "/wizard")

                legacy_troubleshooting = client.get("/legacy/troubleshooting", follow_redirects=False)
                self.assertEqual(legacy_troubleshooting.status_code, 307)
                self.assertEqual(legacy_troubleshooting.headers["location"], "/troubleshooting")

    def test_routes_serve_react_build_and_redirect_legacy_urls_forward(self) -> None:
        with tempfile.TemporaryDirectory(prefix="factory_counter_dist_") as frontend_dist:
            dist_path = Path(frontend_dist)
            assets_path = dist_path / "assets"
            assets_path.mkdir(parents=True, exist_ok=True)
            (dist_path / "index.html").write_text(
                "<!doctype html><html><body><div id='root'>react-cutover-index</div></body></html>",
                encoding="utf-8",
            )
            (assets_path / "app.js").write_text("console.log('cutover');", encoding="utf-8")

            with app_client(extra_env={"FC_FRONTEND_DIST": frontend_dist}) as (client, _temp_dir):
                root = client.get("/")
                self.assertEqual(root.status_code, 200)
                self.assertIn("react-cutover-index", root.text)

                dashboard = client.get("/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("react-cutover-index", dashboard.text)

                app_dashboard = client.get("/app/dashboard")
                self.assertEqual(app_dashboard.status_code, 200)
                self.assertIn("react-cutover-index", app_dashboard.text)

                wizard_redirect = client.get("/wizard/welcome", follow_redirects=False)
                self.assertEqual(wizard_redirect.status_code, 307)
                self.assertEqual(wizard_redirect.headers["location"], "/wizard")

                asset = client.get("/assets/app.js")
                self.assertEqual(asset.status_code, 200)
                self.assertIn("cutover", asset.text)

                legacy_dashboard = client.get("/legacy/dashboard", follow_redirects=False)
                self.assertEqual(legacy_dashboard.status_code, 307)
                self.assertEqual(legacy_dashboard.headers["location"], "/dashboard")
