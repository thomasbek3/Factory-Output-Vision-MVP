from __future__ import annotations

from app.services.count_state_machine import CountEvent
from scripts.audit_factory2_runtime_events import sampled_frame_indices, serialize_event, serialize_track_observation


def test_sampled_frame_indices_respects_window_and_processing_rate() -> None:
    indices = list(
        sampled_frame_indices(
            video_fps=30.0,
            frame_count=300,
            processing_fps=10.0,
            start_seconds=2.0,
            end_seconds=3.0,
        )
    )

    assert indices == [60, 63, 66, 69, 72, 75, 78, 81, 84, 87]


def test_serialize_event_includes_gate_context() -> None:
    class GateDecision:
        decision = "allow_source_token"
        reason = "moving_panel_candidate"
        flags = ["strong_person_panel_crop_classifier"]

    payload = serialize_event(
        event_ts=422.6123,
        event=CountEvent(
            track_id=151,
            count=1,
            reason="approved_delivery_chain",
            bbox=(1.2, 3.4, 5.6, 7.8),
            source_track_id=144,
            source_token_id="source-token-77",
            chain_id="proof-source-track:144",
            source_bbox=(8.0, 9.0, 10.0, 11.0),
            provenance_status="inherited_live_source_token",
            count_authority="source_token_authorized",
        ),
        gate_decision=GateDecision(),
        count_total=17,
    )

    assert payload["event_ts"] == 422.612
    assert payload["track_id"] == 151
    assert payload["count_total"] == 17
    assert payload["gate_decision"]["flags"] == ["strong_person_panel_crop_classifier"]
    assert payload["source_track_id"] == 144
    assert payload["source_token_id"] == "source-token-77"
    assert payload["chain_id"] == "proof-source-track:144"
    assert payload["source_bbox"] == [8.0, 9.0, 10.0, 11.0]
    assert payload["provenance_status"] == "inherited_live_source_token"
    assert payload["count_authority"] == "source_token_authorized"


def test_serialize_track_observation_preserves_zone_and_overlap_metadata() -> None:
    payload = serialize_track_observation(
        event_ts=305.708,
        track_id=108,
        bbox=(659.0, 580.0, 247.0, 42.0),
        confidence=0.91,
        zone="output",
        metadata={
            "person_overlap_ratio": 0.98,
            "outside_person_ratio": 0.02,
            "static_stack_overlap_ratio": 0.1,
        },
    )

    assert payload == {
        "timestamp": 305.708,
        "box_xywh": [659.0, 580.0, 247.0, 42.0],
        "confidence": 0.91,
        "zone": "output",
        "person_overlap": 0.98,
        "outside_person_ratio": 0.02,
        "static_stack_overlap_ratio": 0.1,
    }


def test_serialize_event_includes_predecessor_chain_context() -> None:
    class GateDecision:
        decision = "allow_source_token"
        reason = "moving_panel_candidate"
        flags = ["source_token_allowed_by_person_panel_separation"]

    payload = serialize_event(
        event_ts=120.0,
        event=CountEvent(
            track_id=12,
            count=1,
            reason="approved_delivery_chain",
            bbox=(10.0, 20.0, 30.0, 40.0),
            source_track_id=7,
            chain_id="proof-source-track:7",
            provenance_status="synthetic_approved_chain_token",
            count_authority="runtime_inferred_only",
        ),
        gate_decision=GateDecision(),
        count_total=3,
        provenance={
            "predecessor_chain_track_ids": [5, 7, 12],
            "source_observation_count": 22,
            "output_observation_count": 2,
        },
    )

    assert payload["predecessor_chain_track_ids"] == [5, 7, 12]
    assert payload["source_observation_count"] == 22
    assert payload["output_observation_count"] == 2
    assert payload["count_authority"] == "runtime_inferred_only"
