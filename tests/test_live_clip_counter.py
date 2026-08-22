import unittest

import numpy as np

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
    if "model_path" not in overrides:
        overrides["model_path"] = "/tmp/fake-student.pt"
    settings = LiveClipCounterSettings(
        pixel_change_threshold=overrides.pop("pixel_change_threshold", 0.02),
        cooldown_after_trigger_sec=overrides.pop("cooldown_after_trigger_sec", 16.0),
        **overrides,
    )
    judged: list[dict] = []
    # "hundreds": assert when the clip center sits on a multiple of 100.
    # "first": first clip asserts, everything after refutes (EOF tests).
    assert_rule_overrides = overrides  # (already popped above by caller if used)

    def judge_factory(_config):
        calls = {"n": 0}

        def judge(descriptor):
            judged.append(descriptor)
            calls["n"] += 1
            if settings.model_path == "/tmp/fake-student-first.pt":
                decision = "assert" if calls["n"] == 1 else "refute"
            else:
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
        result3 = counter.process_frame(fake_frame(10), source_timestamp_sec=41.0)  # calm closes -> judge attempt
        self.assertIn("corrupt bundle", str(result3["debug_payload"]["student_load_error"]))
        self.assertEqual(result3["debug_payload"]["verdict"]["judged_by"], "no-judge")

    def test_trigger_opens_window_and_cooldown_judges_once(self) -> None:
        counter = make_counter(cooldown_after_trigger_sec=16.0)
        # Static scene first (baseline).
        counter.process_frame(fake_frame(0), source_timestamp_sec=10.0)
        # Sudden change triggers.
        first = counter.process_frame(fake_frame(200), source_timestamp_sec=12.0)
        self.assertTrue(first["debug_payload"]["triggered"])
        self.assertIsNotNone(first["debug_payload"]["pending_window"])
        # Busy frames inside the cooldown do not judge yet.
        busy = counter.process_frame(fake_frame(200), source_timestamp_sec=20.0)
        self.assertTrue(busy["debug_payload"]["triggered"])
        self.assertEqual(len(counter._judged), 0)
        # Calm vs baseline starts the cooldown; once 16s pass with no new
        # trigger the clip is judged exactly once.
        calm = counter.process_frame(fake_frame(0), source_timestamp_sec=28.0)
        self.assertFalse(calm["debug_payload"]["triggered"])
        after = counter.process_frame(fake_frame(0), source_timestamp_sec=37.0)
        self.assertEqual(len(counter.__dict__["_judged"]), 1)
        self.assertEqual(after["debug_payload"]["verdict"]["judged_by"], "student")
        window = counter.__dict__["_judged"][0]
        self.assertLessEqual(window["start_sec"], 16.0)
        self.assertGreaterEqual(window["end_sec"], 8.0)

    def test_assert_verdict_debounces_into_single_count(self) -> None:
        counter = make_counter()
        counter.process_frame(fake_frame(0), source_timestamp_sec=95.0)
        # Single trigger at 100 -> window (92,108), center exactly 100 -> assert.
        counter.process_frame(fake_frame(255), source_timestamp_sec=100.0)
        closed = counter.process_frame(fake_frame(0), source_timestamp_sec=120.0)
        # The calm frame itself closes the placement: count emits in-band.
        self.assertEqual(closed["count"], 1)
        self.assertEqual([e["count"] for e in closed["count_events"]], [1])
        self.assertEqual(closed["count_events"][0]["count"], counter.total_count)
        # Nothing left over for EOF.
        self.assertEqual(counter.flush(), [])

    def test_refute_verdict_counts_nothing(self) -> None:
        counter = make_counter()
        counter.process_frame(fake_frame(0), source_timestamp_sec=101.0)
        counter.process_frame(fake_frame(9), source_timestamp_sec=103.0)  # center 102 -> refute
        counter.process_frame(fake_frame(9), source_timestamp_sec=120.0)
        events = counter.flush()
        self.assertEqual(events, [])
        self.assertEqual(counter.total_count, 0)

    def test_eof_flush_counts_trailing_assert(self) -> None:
        counter = make_counter(model_path="/tmp/fake-student-first.pt")  # first-clip asserts
        counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=99.0)
        counter.process_frame(np.full((144, 256, 3), 40, np.uint8), source_timestamp_sec=100.0)
        # Stream ends mid-cooldown: flush must close AND finalize the assert.
        events = counter.flush()
        self.assertEqual([e["count"] for e in events], [1])
        self.assertEqual(events[0]["count"], counter.total_count)
        self.assertEqual(counter.flush(), [])  # idempotent

    def test_two_separated_placements_count_twice(self) -> None:
        counter = make_counter()
        counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=1.0)
        # Placement 1: single trigger at 100, calm closes it -> center 100 -> assert.
        counter.process_frame(np.full((144, 256, 3), 40, np.uint8), source_timestamp_sec=100.0)
        first = counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=120.0)
        self.assertEqual([e["count"] for e in first["count_events"]], [1])
        # Placement 2: calm gap, single trigger at 300, calm closes -> center 300.
        counter.process_frame(np.full((144, 256, 3), 40, np.uint8), source_timestamp_sec=300.0)
        second = counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=320.0)
        self.assertEqual([e["count"] for e in second["count_events"]], [2])
        self.assertEqual(counter.total_count, 2)
        self.assertEqual(counter.flush(), [])

    def test_refractory_gap_after_close(self) -> None:
        counter = make_counter(min_candidate_gap_sec=5.0)
        counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=1.0)
        counter.process_frame(np.full((144, 256, 3), 40, np.uint8), source_timestamp_sec=100.0)
        closed = counter.process_frame(np.zeros((144, 256, 3), np.uint8), source_timestamp_sec=116.0)
        self.assertEqual(closed["count"], 1)
        # Residual motion right after close must not instantly reopen a window.
        residual = counter.process_frame(np.full((144, 256, 3), 80, np.uint8), source_timestamp_sec=117.0)
        self.assertIsNone(residual["debug_payload"]["pending_window"])


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
