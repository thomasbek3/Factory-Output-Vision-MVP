from __future__ import annotations

from app.services.perception_gate import GateConfig, GateTrackFeatures, evaluate_track, summarize_gate_decisions


def test_gate_rejects_worker_body_overlap_before_source_token() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=7,
            source_frames=6,
            output_frames=4,
            zones_seen=["source", "transfer", "output"],
            first_zone="source",
            max_displacement=260.0,
            mean_internal_motion=0.22,
            max_internal_motion=0.51,
            detections=12,
            person_overlap_ratio=0.86,
            outside_person_ratio=0.08,
            static_stack_overlap_ratio=0.02,
            static_location_ratio=0.0,
            flow_coherence=0.65,
        ),
        GateConfig(),
    )

    assert decision.decision == "reject"
    assert decision.reason == "worker_body_overlap"
    assert "high_person_overlap" in decision.flags
    assert "not_enough_object_outside_person" in decision.flags


def test_gate_rejects_static_stack_edge_even_when_detector_sees_output() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=3,
            source_frames=0,
            output_frames=18,
            zones_seen=["output"],
            first_zone="output",
            max_displacement=8.0,
            mean_internal_motion=0.01,
            max_internal_motion=0.02,
            detections=18,
            person_overlap_ratio=0.0,
            outside_person_ratio=1.0,
            static_stack_overlap_ratio=0.91,
            static_location_ratio=0.88,
            flow_coherence=0.05,
        ),
        GateConfig(),
    )

    assert decision.decision == "reject"
    assert decision.reason == "static_stack_edge"
    assert "output_only_no_source_token" in decision.flags
    assert "static_location_recurrence" in decision.flags


def test_gate_allows_plausible_source_to_output_panel_track() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=11,
            source_frames=8,
            output_frames=5,
            zones_seen=["source", "transfer", "output"],
            first_zone="source",
            max_displacement=420.0,
            mean_internal_motion=0.19,
            max_internal_motion=0.43,
            detections=15,
            person_overlap_ratio=0.22,
            outside_person_ratio=0.58,
            static_stack_overlap_ratio=0.04,
            static_location_ratio=0.0,
            flow_coherence=0.72,
        ),
        GateConfig(),
    )

    assert decision.decision == "allow_source_token"
    assert decision.reason == "moving_panel_candidate"
    assert decision.evidence["source_frames"] == 8


def test_gate_allows_high_person_overlap_when_panel_protrudes_from_body() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=12,
            source_frames=5,
            output_frames=4,
            zones_seen=["source", "transfer", "output"],
            first_zone="source",
            max_displacement=360.0,
            mean_internal_motion=0.17,
            max_internal_motion=0.39,
            detections=11,
            person_overlap_ratio=0.82,
            outside_person_ratio=0.44,
            static_stack_overlap_ratio=0.03,
            static_location_ratio=0.0,
            flow_coherence=0.68,
        ),
        GateConfig(),
    )

    assert decision.decision == "allow_source_token"
    assert decision.reason == "moving_panel_candidate"
    assert "high_person_overlap" in decision.flags
    assert "person_overlap_with_panel_protrusion" in decision.flags
    assert "source_token_allowed_by_protrusion" in decision.flags


def test_gate_allows_high_person_overlap_when_strong_person_panel_separation_exists() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=15,
            source_frames=38,
            output_frames=1,
            zones_seen=["source", "output"],
            first_zone="source",
            max_displacement=603.294,
            mean_internal_motion=0.337425,
            max_internal_motion=0.730217,
            detections=39,
            person_overlap_ratio=1.0,
            outside_person_ratio=0.0,
            static_stack_overlap_ratio=0.0,
            static_location_ratio=0.333333,
            flow_coherence=0.501419,
            person_panel_recommendation="countable_panel_candidate",
            person_panel_total_candidate_frames=3,
            person_panel_source_candidate_frames=2,
            person_panel_max_visible_nonperson_ratio=0.542531,
            person_panel_max_signal=0.075512,
        ),
        GateConfig(),
    )

    assert decision.decision == "allow_source_token"
    assert decision.reason == "moving_panel_candidate"
    assert "high_person_overlap" in decision.flags
    assert "source_token_allowed_by_person_panel_separation" in decision.flags


def test_gate_marks_high_person_overlap_without_protrusion_uncertain_not_countable() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=13,
            source_frames=5,
            output_frames=4,
            zones_seen=["source", "transfer", "output"],
            first_zone="source",
            max_displacement=360.0,
            mean_internal_motion=0.17,
            max_internal_motion=0.39,
            detections=11,
            person_overlap_ratio=0.82,
            outside_person_ratio=0.28,
            static_stack_overlap_ratio=0.03,
            static_location_ratio=0.0,
            flow_coherence=0.68,
        ),
        GateConfig(),
    )

    assert decision.decision == "uncertain"
    assert decision.reason == "source_to_output_evidence_incomplete"
    assert "high_person_overlap" in decision.flags
    assert "source_token_allowed_by_protrusion" not in decision.flags


def test_gate_keeps_worker_overlap_rejected_when_separation_is_not_persistent() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=16,
            source_frames=9,
            output_frames=1,
            zones_seen=["source", "output"],
            first_zone="source",
            max_displacement=275.0,
            mean_internal_motion=0.18,
            max_internal_motion=0.42,
            detections=10,
            person_overlap_ratio=0.92,
            outside_person_ratio=0.0,
            static_stack_overlap_ratio=0.0,
            static_location_ratio=0.1,
            flow_coherence=0.41,
            person_panel_recommendation="insufficient_visibility",
            person_panel_total_candidate_frames=1,
            person_panel_source_candidate_frames=1,
            person_panel_max_visible_nonperson_ratio=0.491658,
            person_panel_max_signal=0.048451,
        ),
        GateConfig(),
    )

    assert decision.decision == "reject"
    assert decision.reason == "worker_body_overlap"
    assert "source_token_allowed_by_person_panel_separation" not in decision.flags


def test_gate_allows_high_overlap_track_when_crop_classifier_is_strong() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=17,
            source_frames=2,
            output_frames=2,
            zones_seen=["source", "output"],
            first_zone="source",
            max_displacement=188.0,
            mean_internal_motion=0.16,
            max_internal_motion=0.34,
            detections=4,
            person_overlap_ratio=0.94,
            outside_person_ratio=0.0,
            static_stack_overlap_ratio=0.0,
            static_location_ratio=0.0,
            flow_coherence=0.41,
            person_panel_recommendation="not_panel",
            person_panel_crop_recommendation="carried_panel",
            person_panel_crop_positive_crops=2,
            person_panel_crop_total_crops=2,
            person_panel_crop_positive_ratio=1.0,
            person_panel_crop_max_confidence=0.998,
        ),
        GateConfig(),
    )

    assert decision.decision == "allow_source_token"
    assert decision.reason == "moving_panel_candidate"
    assert "source_token_allowed_by_crop_classifier" in decision.flags


def test_gate_demotes_high_overlap_track_to_uncertain_when_crop_classifier_is_strong_but_output_missing() -> None:
    decision = evaluate_track(
        GateTrackFeatures(
            track_id=18,
            source_frames=4,
            output_frames=0,
            zones_seen=["source"],
            first_zone="source",
            max_displacement=188.0,
            mean_internal_motion=0.16,
            max_internal_motion=0.34,
            detections=4,
            person_overlap_ratio=0.94,
            outside_person_ratio=0.0,
            static_stack_overlap_ratio=0.0,
            static_location_ratio=0.0,
            flow_coherence=0.41,
            person_panel_recommendation="not_panel",
            person_panel_crop_recommendation="carried_panel",
            person_panel_crop_positive_crops=4,
            person_panel_crop_total_crops=4,
            person_panel_crop_positive_ratio=1.0,
            person_panel_crop_max_confidence=0.999,
        ),
        GateConfig(),
    )

    assert decision.decision == "uncertain"
    assert decision.reason == "source_without_output_settle"


def test_gate_summary_counts_decisions_and_reasons() -> None:
    decisions = [
        evaluate_track(
            GateTrackFeatures(
                track_id=1,
                source_frames=0,
                output_frames=4,
                zones_seen=["output"],
                first_zone="output",
                max_displacement=1.0,
                mean_internal_motion=0.01,
                max_internal_motion=0.01,
                detections=4,
                static_stack_overlap_ratio=0.9,
                static_location_ratio=0.9,
            ),
            GateConfig(),
        ),
        evaluate_track(
            GateTrackFeatures(
                track_id=2,
                source_frames=3,
                output_frames=0,
                zones_seen=["source"],
                first_zone="source",
                max_displacement=90.0,
                mean_internal_motion=0.12,
                max_internal_motion=0.2,
                detections=5,
            ),
            GateConfig(),
        ),
    ]

    summary = summarize_gate_decisions(decisions)

    assert summary["decision_counts"] == {"allow_source_token": 0, "reject": 1, "uncertain": 1}
    assert summary["reason_counts"]["static_stack_edge"] == 1
    assert summary["reason_counts"]["source_without_output_settle"] == 1
