import unittest

from edge.state import CameraState, apply_state_logic


class TestStateLogic(unittest.TestCase):
    def test_persistent_increment_only(self):
        state = CameraState(camera_id="cam1")
        delta, reset = apply_state_logic(state, measured_count=1, persistence_required=2)
        self.assertEqual(delta, 0)
        self.assertFalse(reset)

        delta, reset = apply_state_logic(state, measured_count=1, persistence_required=2)
        self.assertEqual(delta, 1)
        self.assertFalse(reset)
        self.assertEqual(state.last_committed_count, 1)

    def test_reset_detection(self):
        state = CameraState(camera_id="cam1", last_committed_count=8)
        delta, reset = apply_state_logic(state, measured_count=2, persistence_required=2, reset_threshold=2)
        self.assertEqual(delta, 0)
        self.assertTrue(reset)
        self.assertEqual(state.last_committed_count, 2)


if __name__ == "__main__":
    unittest.main()
