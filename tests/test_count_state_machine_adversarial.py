from __future__ import annotations

from app.services.calibration import CalibrationZones, Gate
from app.services.count_state_machine import CountConfig, CountStateMachine, TrackDetection

SOURCE = [(0, 0), (40, 0), (40, 100), (0, 100)]
OUTPUT = [(60, 0), (100, 0), (100, 100), (60, 100)]


def machine(**overrides) -> CountStateMachine:
    config = CountConfig(
        zones=CalibrationZones(
            source_polygons=[SOURCE],
            output_polygons=[OUTPUT],
            ignore_polygons=[],
        ),
        gate=overrides.pop("gate", None),
        source_min_frames=overrides.pop("source_min_frames", 2),
        output_stable_frames=overrides.pop("output_stable_frames", 2),
        source_overlap_threshold=overrides.pop("source_overlap_threshold", 0.25),
        output_overlap_threshold=overrides.pop("output_overlap_threshold", 0.25),
        stable_center_epsilon=overrides.pop("stable_center_epsilon", 3.0),
        disappear_in_output_frames=overrides.pop("disappear_in_output_frames", 1),
        source_token_ttl_frames=overrides.pop("source_token_ttl_frames", 8),
        resident_match_center_distance=overrides.pop("resident_match_center_distance", 18.0),
        **overrides,
    )
    return CountStateMachine(config)


def det(track_id: int, bbox: tuple[float, float, float, float]) -> TrackDetection:
    return TrackDetection(track_id=track_id, bbox=bbox, confidence=0.9)


def deliver(counter: CountStateMachine, track_id: int = 1, y: float = 20) -> None:
    counter.update([det(track_id, (5, y, 20, 20))])
    counter.update([det(track_id, (10, y, 20, 20))])
    counter.update([det(track_id, (65, y, 20, 20))])
    events = counter.update([det(track_id, (65, y, 20, 20))])
    assert len(events) == 1


def test_new_track_near_counted_resident_is_suppressed_as_reposition() -> None:
    counter = machine()
    deliver(counter, track_id=1)

    # Tracker lost the object and reacquired the same physical resident panel
    # under a new ID while it was being adjusted inside output.
    counter.update([det(44, (68, 22, 20, 20))])
    counter.update([det(44, (72, 22, 20, 20))])
    counter.update([det(44, (70, 22, 20, 20))])

    assert counter.total_count == 1
    assert counter.track_state(44) == "RESIDENT_OUTPUT_OBJECT"


def test_source_token_expires_before_output_and_cannot_count_late() -> None:
    counter = machine(source_token_ttl_frames=2)

    counter.update([det(5, (5, 20, 20, 20))])
    counter.update([det(5, (10, 20, 20, 20))])
    counter.update([])
    counter.update([])
    counter.update([])
    events = counter.update([det(5, (65, 20, 20, 20))])
    events += counter.update([det(5, (65, 20, 20, 20))])

    assert events == []
    assert counter.total_count == 0
    assert "UNCERTAIN_REVIEW" in counter.track_state_path(5)
    assert "token_expired_before_output" in counter.track_uncertain_reasons(5)


def test_id_switch_after_source_token_relinks_and_counts_once() -> None:
    counter = machine(resident_match_center_distance=18.0)

    counter.update([det(1, (5, 20, 20, 20))])
    counter.update([det(1, (10, 20, 20, 20))])
    counter.update([det(1, (42, 20, 10, 20))])
    counter.update([])  # brief occlusion / tracker drop
    counter.update([det(99, (62, 20, 20, 20))])
    events = counter.update([det(99, (64, 20, 20, 20))])
    events += counter.update([det(99, (64, 20, 20, 20))])

    assert len(events) == 1
    assert counter.total_count == 1
    assert counter.track_state(99) == "COUNTED_OUTPUT_RESIDENT"


def test_wrong_gate_direction_records_uncertain_reason_and_counts_zero() -> None:
    counter = machine(gate=Gate(start=(50, 0), end=(50, 100), source_side=-1))

    counter.update([det(7, (5, 20, 20, 20))])
    counter.update([det(7, (10, 20, 20, 20))])
    counter.update([det(7, (65, 20, 20, 20))])
    counter.update([det(7, (65, 20, 20, 20))])

    assert counter.total_count == 0
    assert "missing_gate_crossing" in counter.track_uncertain_reasons(7)
