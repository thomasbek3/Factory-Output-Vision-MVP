from __future__ import annotations

from app.services.calibration import CalibrationZones
from app.services.count_state_machine import CountConfig, CountStateMachine, TrackDetection


def det(track_id: int, box: tuple[float, float, float, float]) -> TrackDetection:
    return TrackDetection(track_id=track_id, bbox=box)


def test_count_state_machine_counts_after_track_becomes_approved_in_output() -> None:
    machine = CountStateMachine(
        CountConfig(
            zones=CalibrationZones(
                source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
                output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
                ignore_polygons=[],
            ),
            source_min_frames=2,
            output_stable_frames=2,
            source_overlap_threshold=0.25,
            output_overlap_threshold=0.25,
        )
    )

    assert machine.update([det(1, (5, 20, 20, 20))], approved_track_ids=set()) == []
    assert machine.update([det(1, (10, 20, 20, 20))], approved_track_ids=set()) == []
    assert machine.update([det(1, (65, 20, 20, 20))], approved_track_ids=set()) == []

    events = machine.update([det(1, (65, 20, 20, 20))], approved_track_ids={1})

    assert len(events) == 1
    assert events[0].track_id == 1
    assert events[0].reason == "stable_in_output"
    assert machine.total_count == 1


def test_count_state_machine_keeps_source_token_alive_while_track_is_continuously_seen() -> None:
    machine = CountStateMachine(
        CountConfig(
            zones=CalibrationZones(
                source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
                output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
                ignore_polygons=[],
            ),
            source_min_frames=2,
            output_stable_frames=2,
            source_overlap_threshold=0.25,
            output_overlap_threshold=0.25,
            disappear_in_output_frames=1,
            source_token_ttl_frames=3,
        )
    )

    for _ in range(6):
        assert machine.update([det(1, (5, 20, 20, 20))], approved_track_ids={1}) == []

    assert machine.update([det(1, (65, 20, 20, 20))], approved_track_ids={1}) == []
    events = machine.update([], approved_track_ids={1})

    assert len(events) == 1
    assert events[0].track_id == 1
    assert events[0].reason == "disappeared_in_output"
    assert machine.total_count == 1
