from __future__ import annotations

from app.services.count_state_machine import CountEvent
from scripts.audit_factory2_runtime_events import sampled_frame_indices, serialize_event


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
        event=CountEvent(track_id=151, count=1, reason="approved_delivery_chain", bbox=(1.2, 3.4, 5.6, 7.8)),
        gate_decision=GateDecision(),
        count_total=17,
    )

    assert payload["event_ts"] == 422.612
    assert payload["track_id"] == 151
    assert payload["count_total"] == 17
    assert payload["gate_decision"]["flags"] == ["strong_person_panel_crop_classifier"]
