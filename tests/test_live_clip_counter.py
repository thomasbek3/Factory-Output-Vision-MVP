import unittest

from app.services.live_clip_counter import (
    LiveClipCounter,
    LiveClipCounterConfigError,
    LiveClipCounterSettings,
    load_settings_from_env,
)


def fake_frame(value: int = 0):
    """Tiny stand-in for a BGR frame: 2x2 pixels, no cv2 needed."""

    class _Frame:
        def __init__(self, value: int) -> None:
            self._value = value

        def __array__(self, dtype=None):
            import numpy as np

            return np.full((36, 64, 3), self._value, dtype=np.uint8)

        shape = (36, 64, 3)

    return _Frame(value)


def make_counter(**overrides) -> LiveClipCounter:
    settings = LiveClipCounterSettings(
        model_path="/tmp/fake-student.pt",
        pixel_change_threshold=overrides.pop("pixel_change_threshold", 0.02),
        cooldown_after_trigger_sec=overrides.pop("cooldown_after_trigger_sec", 16.0),
        **overrides,
    )
    judged: list[dict] = []

    def judge_factory(_config):
        def judge(descriptor):
            judged.append(descriptor)
            # assert placements for clips centered on multiples of 100 sec
            decision = "assert" if int(descriptor["center_sec"]) % 100 == 0 else "refute"
            return {"decision": decision, "score": 0.9 if decision == "assert" else 0.1}

        return judge

    counter = LiveClipCounter(settings=settings, judge_factory=judge_factory)
    counter.__dict__["_judged"] = judged  # test observation hook (no typed attr)
    return counter


class LiveClipCounterUnitTests(unittest.TestCase):
    def test_rejects_invalid_settings(self) -> None:
        with self.assertRaises(LiveClipCounterConfigError):
            make_counter(bracket_sec=0)
        with self.assertRaises(LiveClipCounterConfigError):
            make_counter(pixel_change_threshold=1.5)

    def test_load_error_is_captured_not_raised(self) -> None:
        def bad_factory(_config):
            raise RuntimeError("corrupt bundle")

        settings = LiveClipCounterSettings(model_path="/tmp/bad.pt")
        counter = LiveClipCounter(settings=settings, judge_factory=bad_factory)
        counter.process_frame(fake_frame(10), source_timestamp_sec=0.0)
        counter.process_frame(fake_frame(250), source_timestamp_sec=20.0)  # trigger
        result3 = counter.process_frame(fake_frame(250), source_timestamp_sec=40.0)  # judge attempt
        self.assertIn("corrupt bundle", str(result3["debug_payload"]["student_load_error"]))
        self.assertEqual(result3["debug_payload"]["verdict"]["judged_by"], "no-judge")

    def test_trigger_opens_window_and_cooldown_judges_once(self) -> None:
        counter = make_counter(cooldown_after_trigger_sec=16.0)
        # Static scene first (baseline).
        counter.process_frame(fake_frame(0), source_timestamp_sec=10.0)
        # Sudden change triggers.
        first = counter.process_frame(fake_frame(200), source_timestamp_sec=12.0)
        self.assertTrue(first["debug_payload"]["triggered"])
        self.assertIsNotNone(first["debug_payload"]["pending_clip"])
        # Calm frames inside the cooldown do not judge yet.
        calm = counter.process_frame(fake_frame(200), source_timestamp_sec=20.0)
        self.assertFalse(calm["debug_payload"]["triggered"])
        self.assertEqual(len(counter._judged), 0)
        # After the cooldown the clip is judged exactly once.
        after = counter.process_frame(fake_frame(200), source_timestamp_sec=29.0)
        self.assertEqual(len(counter._judged), 1)
        self.assertEqual(after["debug_payload"]["verdict"]["judged_by"], "student")
        window = counter._judged[0]
        self.assertLessEqual(window["start_sec"], 12.0 + 4.0)
        self.assertGreaterEqual(window["end_sec"], 12.0 - 4.0)

    def test_assert_verdict_debounces_into_single_count(self) -> None:
        counter = make_counter()
        counter.process_frame(fake_frame(0), source_timestamp_sec=95.0)
        counter.process_frame(fake_frame(255), source_timestamp_sec=102.0)  # window (98,102) center 100
        counter.process_frame(fake_frame(255), source_timestamp_sec=120.0)  # cooldown elapsed -> assert
        events = counter.flush()
        self.assertEqual([e["count"] for e in events], [1])
        self.assertEqual(events[0]["count"], counter.total_count)

    def test_refute_verdict_counts_nothing(self) -> None:
        counter = make_counter()
        counter.process_frame(fake_frame(0), source_timestamp_sec=101.0)
        counter.process_frame(fake_frame(9), source_timestamp_sec=103.0)  # center 102 -> refute
        counter.process_frame(fake_frame(9), source_timestamp_sec=120.0)
        events = counter.flush()
        self.assertEqual(events, [])
        self.assertEqual(counter.total_count, 0)


class LiveClipCounterEnvTests(unittest.TestCase):
    def test_env_roundtrip(self) -> None:
        import os

        old = os.environ.get("FC_CLIP_STUDENT_MODEL_PATH")
        try:
            os.environ["FC_CLIP_STUDENT_MODEL_PATH"] = "/tmp/x.pt"
            os.environ["FC_CLIP_BRACKET_SEC"] = "6"
            settings = load_settings_from_env()
            self.assertEqual(settings.model_path, "/tmp/x.pt")
            self.assertEqual(settings.bracket_sec, 6.0)
        finally:
            if old is None:
                os.environ.pop("FC_CLIP_STUDENT_MODEL_PATH", None)
            else:
                os.environ["FC_CLIP_STUDENT_MODEL_PATH"] = old
            os.environ.pop("FC_CLIP_BRACKET_SEC", None)


if __name__ == "__main__":
    unittest.main()
