from __future__ import annotations

import unittest

from app.services.calibration import (
    CalibrationZones,
    Gate,
    box_area,
    box_center,
    box_polygon_overlap_fraction,
    gate_crossed_allowed_direction,
    point_in_polygon,
    zone_membership,
)
from app.services.count_state_machine import CountConfig, CountStateMachine, TrackDetection


SOURCE = [(0, 0), (40, 0), (40, 100), (0, 100)]
OUTPUT = [(60, 0), (100, 0), (100, 100), (60, 100)]
IGNORE = [(45, 0), (55, 0), (55, 100), (45, 100)]


def machine() -> CountStateMachine:
    return CountStateMachine(
        CountConfig(
            zones=CalibrationZones(
                source_polygons=[SOURCE],
                output_polygons=[OUTPUT],
                ignore_polygons=[],
            ),
            source_min_frames=2,
            output_stable_frames=2,
            source_overlap_threshold=0.25,
            output_overlap_threshold=0.25,
            stable_center_epsilon=3.0,
            disappear_in_output_frames=1,
        )
    )


def det(track_id: int, bbox: tuple[float, float, float, float]) -> TrackDetection:
    return TrackDetection(track_id=track_id, bbox=bbox, confidence=0.9)


class CalibrationGeometryTests(unittest.TestCase):
    def test_geometry_helpers_and_zone_membership(self) -> None:
        self.assertEqual(box_center((10, 20, 30, 40)), (25.0, 40.0))
        self.assertEqual(box_area((10, 20, 30, 40)), 1200.0)

        self.assertTrue(point_in_polygon((10, 10), SOURCE))
        self.assertFalse(point_in_polygon((50, 10), SOURCE))

        self.assertGreater(box_polygon_overlap_fraction((5, 5, 20, 20), SOURCE), 0.9)
        self.assertLess(box_polygon_overlap_fraction((42, 5, 10, 20), SOURCE), 0.1)

        membership = zone_membership(
            (65, 10, 15, 20),
            CalibrationZones(
                source_polygons=[SOURCE],
                output_polygons=[OUTPUT],
                ignore_polygons=[IGNORE],
            ),
        )
        self.assertGreater(membership.output_overlap, 0.9)
        self.assertEqual(membership.source_overlap, 0.0)
        self.assertFalse(membership.center_in_ignore)

    def test_gate_allowed_direction(self) -> None:
        gate = Gate(start=(50, 0), end=(50, 100), source_side=1)
        self.assertTrue(gate_crossed_allowed_direction((40, 50), (60, 50), gate))
        self.assertFalse(gate_crossed_allowed_direction((60, 50), (40, 50), gate))
        self.assertFalse(gate_crossed_allowed_direction((40, 50), (45, 50), gate))


class CountStateMachineTests(unittest.TestCase):
    def test_source_to_output_to_stable_counts_one(self) -> None:
        counter = machine()

        self.assertEqual(counter.update([det(1, (5, 20, 20, 20))]), [])
        self.assertEqual(counter.update([det(1, (10, 20, 20, 20))]), [])
        self.assertEqual(counter.update([det(1, (64, 20, 20, 20))]), [])
        events = counter.update([det(1, (65, 20, 20, 20))])

        self.assertEqual(len(events), 1)
        self.assertEqual(counter.total_count, 1)
        self.assertEqual(events[0].reason, "stable_in_output")

    def test_reposition_inside_output_after_count_does_not_count_again(self) -> None:
        counter = machine()

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])
        self.assertEqual(len(counter.update([det(1, (65, 20, 20, 20))])), 1)

        self.assertEqual(counter.update([det(1, (78, 25, 20, 20))]), [])
        self.assertEqual(counter.update([det(1, (80, 25, 20, 20))]), [])

        self.assertEqual(counter.total_count, 1)

    def test_object_first_seen_in_output_counts_zero(self) -> None:
        counter = machine()

        counter.update([det(10, (65, 20, 20, 20))])
        counter.update([det(10, (65, 20, 20, 20))])
        counter.update([det(10, (68, 20, 20, 20))])

        self.assertEqual(counter.total_count, 0)

    def test_source_to_output_disappears_inside_output_counts_one(self) -> None:
        counter = machine()

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])
        events = counter.update([])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].reason, "disappeared_in_output")
        self.assertEqual(counter.total_count, 1)

    def test_source_to_output_then_neutral_then_missing_counts_zero(self) -> None:
        counter = machine()

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])
        counter.update([det(1, (45, 20, 10, 20))])
        events = counter.update([])

        self.assertEqual(events, [])
        self.assertEqual(counter.total_count, 0)

    def test_configured_gate_opposite_direction_prevents_count(self) -> None:
        counter = CountStateMachine(
            CountConfig(
                zones=CalibrationZones(
                    source_polygons=[SOURCE],
                    output_polygons=[OUTPUT],
                    ignore_polygons=[],
                ),
                gate=Gate(start=(50, 0), end=(50, 100), source_side=-1),
                source_min_frames=2,
                output_stable_frames=2,
                source_overlap_threshold=0.25,
                output_overlap_threshold=0.25,
                stable_center_epsilon=3.0,
                disappear_in_output_frames=1,
            )
        )

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])
        self.assertEqual(counter.update([det(1, (65, 20, 20, 20))]), [])
        self.assertEqual(counter.update([]), [])

        self.assertEqual(counter.total_count, 0)

    def test_two_separate_source_origin_deliveries_count_two(self) -> None:
        counter = machine()

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])
        counter.update([det(1, (65, 20, 20, 20))])

        counter.update([det(2, (5, 50, 20, 20))])
        counter.update([det(2, (10, 50, 20, 20))])
        counter.update([det(2, (65, 50, 20, 20))])
        counter.update([det(2, (65, 50, 20, 20))])

        self.assertEqual(counter.total_count, 2)

    def test_output_zone_movement_without_source_token_counts_zero(self) -> None:
        counter = machine()

        counter.update([det(3, (65, 20, 20, 20))])
        counter.update([det(3, (80, 20, 20, 20))])
        counter.update([det(3, (78, 20, 20, 20))])
        counter.update([det(3, (80, 20, 20, 20))])

        self.assertEqual(counter.total_count, 0)

    def test_approved_delivery_chain_does_not_double_count_overlapping_resident(self) -> None:
        counter = CountStateMachine(
            CountConfig(
                zones=CalibrationZones(
                    source_polygons=[SOURCE],
                    output_polygons=[OUTPUT],
                    ignore_polygons=[],
                ),
                source_min_frames=2,
                output_stable_frames=2,
                source_overlap_threshold=0.25,
                output_overlap_threshold=0.25,
                stable_center_epsilon=3.0,
                disappear_in_output_frames=1,
                resident_match_center_distance=10.0,
                resident_output_overlap_threshold=0.4,
            )
        )

        counter.update([det(1, (5, 20, 20, 20)), det(2, (5, 50, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20)), det(2, (10, 50, 20, 20))])

        first = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:1",
            source_track_id=1,
            output_track_id=3,
            output_bbox=(60, 20, 40, 20),
        )
        second = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:2",
            source_track_id=2,
            output_track_id=4,
            output_bbox=(80, 20, 40, 20),
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(counter.total_count, 1)

    def test_approved_delivery_chain_can_count_later_overlapping_delivery(self) -> None:
        counter = CountStateMachine(
            CountConfig(
                zones=CalibrationZones(
                    source_polygons=[SOURCE],
                    output_polygons=[OUTPUT],
                    ignore_polygons=[],
                ),
                source_min_frames=2,
                output_stable_frames=2,
                source_overlap_threshold=0.25,
                output_overlap_threshold=0.25,
                stable_center_epsilon=3.0,
                disappear_in_output_frames=1,
                resident_match_center_distance=10.0,
                resident_output_overlap_threshold=0.4,
            )
        )

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])
        first = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:1",
            source_track_id=1,
            output_track_id=3,
            output_bbox=(60, 20, 40, 20),
        )

        for _ in range(6):
            counter.update([])

        counter.update([det(2, (5, 50, 20, 20))])
        counter.update([det(2, (10, 50, 20, 20))])
        second = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:2",
            source_track_id=2,
            output_track_id=4,
            output_bbox=(80, 20, 40, 20),
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(counter.total_count, 2)

    def test_approved_delivery_chain_event_carries_source_token_provenance(self) -> None:
        counter = CountStateMachine(
            CountConfig(
                zones=CalibrationZones(
                    source_polygons=[SOURCE],
                    output_polygons=[OUTPUT],
                    ignore_polygons=[],
                ),
                source_min_frames=2,
                output_stable_frames=2,
                source_overlap_threshold=0.25,
                output_overlap_threshold=0.25,
                stable_center_epsilon=3.0,
                disappear_in_output_frames=1,
                resident_match_center_distance=10.0,
                resident_output_overlap_threshold=0.4,
            )
        )

        counter.update([det(1, (5, 20, 20, 20))])
        counter.update([det(1, (10, 20, 20, 20))])

        event = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:1",
            source_track_id=1,
            output_track_id=3,
            output_bbox=(60, 20, 40, 20),
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.reason, "approved_delivery_chain")
        self.assertEqual(event.source_track_id, 1)
        self.assertEqual(event.chain_id, "proof-source-track:1")
        self.assertEqual(event.source_token_id, "source-token-1")
        self.assertEqual(event.source_bbox, (10, 20, 20, 20))
        self.assertEqual(event.provenance_status, "inherited_live_source_token")

    def test_approved_delivery_chain_marks_synthetic_fallback_when_source_token_missing(self) -> None:
        counter = CountStateMachine(
            CountConfig(
                zones=CalibrationZones(
                    source_polygons=[SOURCE],
                    output_polygons=[OUTPUT],
                    ignore_polygons=[],
                ),
                source_min_frames=2,
                output_stable_frames=2,
                source_overlap_threshold=0.25,
                output_overlap_threshold=0.25,
                stable_center_epsilon=3.0,
                disappear_in_output_frames=1,
                resident_match_center_distance=10.0,
                resident_output_overlap_threshold=0.4,
            )
        )

        event = counter.commit_approved_delivery_chain(
            chain_id="proof-source-track:77",
            source_track_id=77,
            output_track_id=88,
            output_bbox=(60, 20, 40, 20),
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.source_track_id, 77)
        self.assertEqual(event.provenance_status, "synthetic_approved_chain_token")
        self.assertEqual(event.source_bbox, (60, 20, 40, 20))


if __name__ == "__main__":
    unittest.main()
