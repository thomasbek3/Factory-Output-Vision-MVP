from __future__ import annotations

from pathlib import Path

from scripts.assess_blind_prediction_viability import assess_viability


def _screen(*, active_recommendation: str, static_recommendation: str) -> dict:
    return {
        "sample_count": 80,
        "models": [
            {
                "model_path": "models/active_a.pt",
                "confidence_summaries": [
                    {
                        "confidence": 0.25,
                        "images_with_detections": 0 if "failed" in active_recommendation else 30,
                        "sample_count": 80,
                        "detection_rate": 0.0 if "failed" in active_recommendation else 0.375,
                        "total_detections": 0 if "failed" in active_recommendation else 34,
                        "recommendation": active_recommendation,
                    }
                ],
            },
            {
                "model_path": "models/wire_mesh_panel.pt",
                "confidence_summaries": [
                    {
                        "confidence": 0.25,
                        "images_with_detections": 80,
                        "sample_count": 80,
                        "detection_rate": 1.0,
                        "total_detections": 656,
                        "recommendation": static_recommendation,
                    }
                ],
            },
        ],
    }


def _diagnostic(timestamps: list[float], *, eof_count: int = 0) -> dict:
    events = [
        {
            "event_ts": timestamp,
            "reason": "dead_track_event",
            "travel_px": 1.0 if index % 2 == 0 else 25.0,
        }
        for index, timestamp in enumerate(timestamps)
    ]
    events.extend(
        {
            "event_ts": timestamps[-1] if timestamps else 0.0,
            "reason": "end_of_stream_active_track_event",
            "travel_px": 0.0,
        }
        for _index in range(eof_count)
    )
    return {
        "current_state": "DEMO_COMPLETE",
        "observed_event_count": len(events),
        "events": events,
    }


def test_static_detector_failure_refuses_numeric_blind_prediction() -> None:
    payload = assess_viability(
        detector_screen=_screen(
            active_recommendation="transfer_failed_build_video_specific_detector",
            static_recommendation="broad_or_static_detector_risk_requires_runtime_diagnostic",
        ),
        detector_screen_path=Path("data/reports/screen.json"),
        diagnostic_payloads=[
            (Path("data/reports/diag30.json"), _diagnostic([1.0, 2.0, 3.0], eof_count=2)),
            (Path("data/reports/diag60.json"), _diagnostic([1.0, 2.0], eof_count=2)),
        ],
        static_risk_models={"models/wire_mesh_panel.pt", "wire_mesh_panel.pt"},
    )

    assert payload["status"] == "no_valid_blind_prediction"
    assert payload["numeric_prediction_allowed"] is False
    assert payload["transfer_summary"]["active_transfer_failed"] is True
    assert payload["transfer_summary"]["static_detector_risk"] is True
    assert payload["runtime_diagnostics"]["parameter_sensitive"] is True
    assert payload["runtime_diagnostics"]["non_eof_event_count_spread"] == 1
    assert payload["runtime_diagnostics"]["summaries"][0]["non_eof_event_count"] == 3
    assert payload["runtime_diagnostics"]["summaries"][0]["eof_event_count"] == 2


def test_plausible_active_detector_allows_numeric_prediction_path() -> None:
    payload = assess_viability(
        detector_screen=_screen(
            active_recommendation="plausible_transfer_candidate_run_fast_diagnostic",
            static_recommendation="broad_or_static_detector_risk_requires_runtime_diagnostic",
        ),
        detector_screen_path=Path("data/reports/screen.json"),
        diagnostic_payloads=[],
        static_risk_models={"models/wire_mesh_panel.pt", "wire_mesh_panel.pt"},
    )

    assert payload["status"] == "plausible_prediction_path_available"
    assert payload["numeric_prediction_allowed"] is True
    assert payload["recommendation"] == "continue_with_plausible_runtime_diagnostic"


def test_dead_active_detectors_without_diagnostic_route_to_specific_detector() -> None:
    payload = assess_viability(
        detector_screen=_screen(
            active_recommendation="transfer_failed_build_video_specific_detector",
            static_recommendation="broad_or_static_detector_risk_requires_runtime_diagnostic",
        ),
        detector_screen_path=Path("data/reports/screen.json"),
        diagnostic_payloads=[],
        static_risk_models={"models/wire_mesh_panel.pt", "wire_mesh_panel.pt"},
    )

    assert payload["status"] == "needs_video_specific_detector_before_prediction"
    assert payload["numeric_prediction_allowed"] is False
    assert payload["runtime_diagnostics"]["summaries"] == []
