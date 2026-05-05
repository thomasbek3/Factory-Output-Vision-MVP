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
            "FC_DEMO_LOOP": os.environ.get("FC_DEMO_LOOP"),
            "FC_EVENT_COUNT_RULE": os.environ.get("FC_EVENT_COUNT_RULE"),
        }
        try:
            os.environ["FC_COUNTING_MODE"] = "event_based"
            os.environ["FC_RUNTIME_CALIBRATION_PATH"] = "/tmp/factory2-runtime-calibration.json"
            os.environ.pop("FC_YOLO_CONF_THRESHOLD", None)

            self.assertEqual(settings.get_yolo_conf_threshold(), 0.25)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_demo_loop_defaults_off_for_event_based_runtime_calibration(self) -> None:
        previous = {
            "FC_COUNTING_MODE": os.environ.get("FC_COUNTING_MODE"),
            "FC_RUNTIME_CALIBRATION_PATH": os.environ.get("FC_RUNTIME_CALIBRATION_PATH"),
            "FC_DEMO_LOOP": os.environ.get("FC_DEMO_LOOP"),
            "FC_EVENT_COUNT_RULE": os.environ.get("FC_EVENT_COUNT_RULE"),
        }
        try:
            os.environ["FC_COUNTING_MODE"] = "event_based"
            os.environ["FC_RUNTIME_CALIBRATION_PATH"] = "/tmp/factory2-runtime-calibration.json"
            os.environ.pop("FC_DEMO_LOOP", None)

            self.assertFalse(settings.is_demo_loop_enabled())
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_demo_loop_env_can_force_looping_back_on(self) -> None:
        previous = {
            "FC_COUNTING_MODE": os.environ.get("FC_COUNTING_MODE"),
            "FC_RUNTIME_CALIBRATION_PATH": os.environ.get("FC_RUNTIME_CALIBRATION_PATH"),
            "FC_DEMO_LOOP": os.environ.get("FC_DEMO_LOOP"),
            "FC_EVENT_COUNT_RULE": os.environ.get("FC_EVENT_COUNT_RULE"),
        }
        try:
            os.environ["FC_COUNTING_MODE"] = "event_based"
            os.environ["FC_RUNTIME_CALIBRATION_PATH"] = "/tmp/factory2-runtime-calibration.json"
            os.environ["FC_DEMO_LOOP"] = "1"

            self.assertTrue(settings.is_demo_loop_enabled())
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_event_count_rule_defaults_to_auto(self) -> None:
        previous = os.environ.get("FC_EVENT_COUNT_RULE")
        try:
            os.environ.pop("FC_EVENT_COUNT_RULE", None)

            self.assertEqual(settings.get_event_count_rule(), "auto")
        finally:
            if previous is None:
                os.environ.pop("FC_EVENT_COUNT_RULE", None)
            else:
                os.environ["FC_EVENT_COUNT_RULE"] = previous

    def test_event_count_rule_accepts_placed_and_stayed(self) -> None:
        previous = os.environ.get("FC_EVENT_COUNT_RULE")
        try:
            os.environ["FC_EVENT_COUNT_RULE"] = "placed_and_stayed"

            self.assertEqual(settings.get_event_count_rule(), "placed_and_stayed")
        finally:
            if previous is None:
                os.environ.pop("FC_EVENT_COUNT_RULE", None)
            else:
                os.environ["FC_EVENT_COUNT_RULE"] = previous

    def test_event_count_rule_rejects_unknown_values(self) -> None:
        previous = os.environ.get("FC_EVENT_COUNT_RULE")
        try:
            os.environ["FC_EVENT_COUNT_RULE"] = "magic"

            with self.assertRaises(ValueError):
                settings.get_event_count_rule()
        finally:
            if previous is None:
                os.environ.pop("FC_EVENT_COUNT_RULE", None)
            else:
                os.environ["FC_EVENT_COUNT_RULE"] = previous
