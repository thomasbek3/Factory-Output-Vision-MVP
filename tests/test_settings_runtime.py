from __future__ import annotations

import os
import unittest

from app.core import settings


class RuntimeSettingsTests(unittest.TestCase):
    def test_event_based_runtime_calibration_uses_factory2_detector_default(self) -> None:
        previous = {
            "FC_COUNTING_MODE": os.environ.get("FC_COUNTING_MODE"),
            "FC_RUNTIME_CALIBRATION_PATH": os.environ.get("FC_RUNTIME_CALIBRATION_PATH"),
            "FC_YOLO_CONF_THRESHOLD": os.environ.get("FC_YOLO_CONF_THRESHOLD"),
        }
        try:
            os.environ["FC_COUNTING_MODE"] = "event_based"
            os.environ["FC_RUNTIME_CALIBRATION_PATH"] = "/tmp/factory2-runtime-calibration.json"
            os.environ.pop("FC_YOLO_CONF_THRESHOLD", None)

            self.assertEqual(settings.get_yolo_conf_threshold(), 0.15)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
