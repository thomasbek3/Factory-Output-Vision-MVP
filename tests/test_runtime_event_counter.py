from __future__ import annotations

import numpy as np

from app.services.calibration import CalibrationZones
from app.services.runtime_event_counter import RuntimeEventCounter, crop_live_separation_inputs


def test_crop_live_separation_inputs_keeps_boxes_in_crop_coordinates() -> None:
    frame = np.zeros((200, 300, 3), dtype=np.uint8)

    crop = crop_live_separation_inputs(
        frame,
        panel_box=(120.0, 80.0, 30.0, 20.0),
        person_box=(100.0, 60.0, 80.0, 90.0),
        margin_ratio=0.0,
        min_margin_px=10,
    )

    assert crop.left == 90
    assert crop.top == 50
    assert crop.image.shape[:2] == (110, 100)
    assert crop.panel_box == (30.0, 30.0, 30.0, 20.0)
    assert crop.person_box == (10.0, 10.0, 80.0, 90.0)


def test_runtime_event_counter_counts_worker_overlap_track_only_after_live_separation() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )
    calls: list[str] = []

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        calls.append(zone)
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=None,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 1
    assert result.events[0].reason == "stable_in_output"
    assert result.gate_decisions[1].decision == "allow_source_token"
    assert result.gate_decisions[1].reason == "moving_panel_candidate"
    assert "source" in calls[:2]


def test_runtime_event_counter_reuses_nearby_live_separation_samples() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )
    separation_calls: list[tuple[str, tuple[float, float, float, float]]] = []

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        separation_calls.append((zone, panel_box_xywh))
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=None,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (8, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert separation_calls == [
        ("source", (5.0, 20.0, 20.0, 20.0)),
        ("output", (65.0, 20.0, 20.0, 20.0)),
    ]


def test_runtime_event_counter_reuses_stable_live_separation_across_configured_gap() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )
    separation_calls: list[tuple[str, tuple[float, float, float, float]]] = []

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        separation_calls.append((zone, panel_box_xywh))
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=None,
        live_analysis_cache_max_gap_frames=5,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    for x in (5, 6, 7, 8, 9):
        counter.process_frame(frame=frame, detections=[{"box": (x, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert separation_calls == [
        ("source", (5.0, 20.0, 20.0, 20.0)),
        ("output", (65.0, 20.0, 20.0, 20.0)),
    ]


def test_runtime_event_counter_skips_live_separation_for_clear_nonoverlap_tracks() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fail_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        raise AssertionError("live separation should not run for a clear non-overlap track")

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fail_separation_analyzer,
        crop_classifier=None,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    far_person_boxes = [(80.0, 0.0, 20.0, 20.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=far_person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=far_person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=far_person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.gate_decisions[1].decision == "allow_source_token"


def test_runtime_event_counter_counts_approved_delivery_chain_without_extra_output_settle() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 1


def test_runtime_event_counter_keeps_worker_overlap_track_blocked_without_live_separation() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "worker_body_overlap",
            "visible_nonperson_ratio": 0.02,
            "estimated_visible_nonperson_region_signal": 0.001,
            "reason_strings": ["candidate stays swallowed by person silhouette"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=None,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 0
    assert result.events == []
    assert result.gate_decisions[1].decision == "reject"
    assert result.gate_decisions[1].reason == "worker_body_overlap"


def test_runtime_event_counter_counts_worker_overlap_track_with_crop_classifier() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "worker_body_overlap",
            "visible_nonperson_ratio": 0.01,
            "estimated_visible_nonperson_region_signal": 0.001,
            "reason_strings": ["candidate stays swallowed by person silhouette"],
        }

    def fake_crop_classifier(*, image, panel_box_xywh, zone):
        return {
            "recommendation": "carried_panel",
            "prediction_count": 1,
            "carried_panel_count": 1,
            "worker_only_count": 0,
            "carried_panel_ratio": 1.0,
            "carried_panel_max_confidence": 0.999,
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=fake_crop_classifier,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.gate_decisions[1].decision == "allow_source_token"
    assert "source_token_allowed_by_crop_classifier" in result.gate_decisions[1].flags


def test_runtime_event_counter_reuses_nearby_crop_classifier_samples() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )
    crop_calls: list[tuple[str, tuple[float, float, float, float]]] = []

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "worker_body_overlap",
            "visible_nonperson_ratio": 0.01,
            "estimated_visible_nonperson_region_signal": 0.001,
            "reason_strings": ["candidate stays swallowed by person silhouette"],
        }

    def fake_crop_classifier(*, image, panel_box_xywh, zone):
        crop_calls.append((zone, panel_box_xywh))
        return {
            "recommendation": "carried_panel",
            "prediction_count": 1,
            "carried_panel_count": 1,
            "worker_only_count": 0,
            "carried_panel_ratio": 1.0,
            "carried_panel_max_confidence": 0.999,
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=fake_crop_classifier,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (8, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert crop_calls == [
        ("source", (5.0, 20.0, 20.0, 20.0)),
        ("output", (65.0, 20.0, 20.0, 20.0)),
    ]


def test_runtime_event_counter_keeps_worker_overlap_track_blocked_when_crop_classifier_is_worker_only() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "worker_body_overlap",
            "visible_nonperson_ratio": 0.01,
            "estimated_visible_nonperson_region_signal": 0.001,
            "reason_strings": ["candidate stays swallowed by person silhouette"],
        }

    def fake_crop_classifier(*, image, panel_box_xywh, zone):
        return {
            "recommendation": "worker_only",
            "prediction_count": 1,
            "carried_panel_count": 0,
            "worker_only_count": 1,
            "carried_panel_ratio": 0.0,
            "carried_panel_max_confidence": 0.0,
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=fake_crop_classifier,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 0
    assert result.events == []
    assert result.gate_decisions[1].decision == "reject"
    assert result.gate_decisions[1].reason == "worker_body_overlap"


def test_runtime_event_counter_merges_split_worker_overlap_chain_with_crop_classifier() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "worker_body_overlap",
            "visible_nonperson_ratio": 0.0,
            "estimated_visible_nonperson_region_signal": 0.0,
            "reason_strings": ["candidate stays swallowed by person silhouette"],
        }

    def fake_crop_classifier(*, image, panel_box_xywh, zone):
        return {
            "recommendation": "carried_panel",
            "prediction_count": 1,
            "carried_panel_count": 1,
            "worker_only_count": 0,
            "carried_panel_ratio": 1.0,
            "carried_panel_max_confidence": 0.999,
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        separation_analyzer=fake_separation_analyzer,
        crop_classifier=fake_crop_classifier,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].reason == "approved_delivery_chain"
    assert result.gate_decisions[2].decision == "allow_source_token"
    assert "source_token_allowed_by_crop_classifier" in result.gate_decisions[2].flags


def test_runtime_event_counter_bridges_brief_detection_dropout_before_output() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=120.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 1


def test_runtime_event_counter_bridges_longer_split_gap_before_output() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    for _ in range(15):
        counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 2
    assert result.events[0].reason == "approved_delivery_chain"
    assert result.gate_decisions[2].decision == "allow_source_token"


def test_runtime_event_counter_merges_source_track_into_output_successor() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    follow_up = counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 2
    assert result.events[0].reason == "approved_delivery_chain"
    assert follow_up.events == []


def test_runtime_event_counter_counts_proof_grade_split_delivery_without_waiting_for_settle() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 2
    assert result.events[0].reason == "approved_delivery_chain"
    assert result.gate_decisions[2].decision == "allow_source_token"


def test_runtime_event_counter_prefers_output_zone_when_output_overlap_is_stronger() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=1,
        output_stable_frames=1,
        tracker_match_distance=80.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (25, 20, 60, 20), "confidence": 0.9}], person_boxes=person_boxes)

    accumulator = counter._gate_accumulators[1]
    assert accumulator.source_frames == 1
    assert accumulator.output_frames == 1
    assert accumulator.last_zone == "output"


def test_runtime_event_counter_uses_stronger_live_mesh_signal_when_weighted_signal_is_low() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate" if zone == "source" else "worker_body_overlap",
            "visible_nonperson_ratio": 0.55 if zone == "source" else 0.0,
            "estimated_visible_nonperson_region_signal": 0.02 if zone == "source" else 0.0,
            "mesh_signal_nonperson_score": 0.055 if zone == "source" else 0.0,
            "mesh_signal_border_score": 0.07 if zone == "source" else 0.0,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=1,
        tracker_match_distance=100.0,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (10, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.gate_decisions[1].decision == "allow_source_token"


def test_runtime_event_counter_merges_source_track_into_short_source_output_successor() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        tracker_max_missing_frames=1,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (35, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 2
    assert result.events[0].reason == "approved_delivery_chain"
    assert result.gate_decisions[2].decision == "allow_source_token"


def test_runtime_event_counter_merges_multi_hop_source_chain_before_output_successor() -> None:
    zones = CalibrationZones(
        source_polygons=[[(0, 0), (40, 0), (40, 100), (0, 100)]],
        output_polygons=[[(60, 0), (100, 0), (100, 100), (60, 100)]],
        ignore_polygons=[],
    )

    def fake_separation_analyzer(*, image, panel_box_xywh, person_box_xywh, zone):
        return {
            "zone": zone,
            "separation_decision": "separable_panel_candidate",
            "visible_nonperson_ratio": 0.42,
            "estimated_visible_nonperson_region_signal": 0.08,
            "reason_strings": ["synthetic outside-silhouette panel evidence"],
        }

    counter = RuntimeEventCounter(
        zones=zones,
        gate=None,
        source_min_frames=2,
        output_stable_frames=2,
        tracker_match_distance=40.0,
        tracker_max_missing_frames=1,
        separation_analyzer=fake_separation_analyzer,
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    person_boxes = [(0.0, 0.0, 100.0, 100.0)]

    counter.process_frame(frame=frame, detections=[{"box": (5, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (15, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (35, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (25, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[], person_boxes=person_boxes)
    counter.process_frame(frame=frame, detections=[{"box": (35, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)
    result = counter.process_frame(frame=frame, detections=[{"box": (65, 20, 20, 20), "confidence": 0.9}], person_boxes=person_boxes)

    assert counter.total_count == 1
    assert len(result.events) == 1
    assert result.events[0].track_id == 3
    assert result.events[0].reason == "approved_delivery_chain"
    assert result.gate_decisions[3].decision == "allow_source_token"
