from __future__ import annotations

from pathlib import Path

from scripts.build_failed_blind_run_learning_packet import build_html, build_packet


def _write_json(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_failed_blind_packet_excludes_eof_and_links_nearest_motion_window(tmp_path: Path) -> None:
    motion = tmp_path / "motion.json"
    diagnostic = tmp_path / "diagnostic.json"
    viability = tmp_path / "viability.json"

    _write_json(
        motion,
        """
        {
          "events": [
            {"event_id": "motion-a", "center_timestamp": 10.0, "start_timestamp": 4.0, "end_timestamp": 16.0, "score": 0.1, "sheet_path": "sheet-a.jpg", "clip_path": "clip-a.mp4"},
            {"event_id": "motion-b", "center_timestamp": 40.0, "start_timestamp": 34.0, "end_timestamp": 46.0, "score": 0.2, "sheet_path": "sheet-b.jpg", "clip_path": "clip-b.mp4"}
          ]
        }
        """,
    )
    _write_json(
        diagnostic,
        """
        {
          "events": [
            {"event_ts": 38.0, "track_id": 7, "reason": "dead_track_event", "travel_px": 3.0, "frames_seen": 12, "runtime_total_after_event": 1},
            {"event_ts": 100.0, "reason": "end_of_stream_active_track_event", "runtime_total_after_event": 2}
          ]
        }
        """,
    )
    _write_json(
        viability,
        """
        {
          "status": "no_valid_blind_prediction",
          "numeric_prediction_allowed": false,
          "recommendation": "route_to_learning_library"
        }
        """,
    )

    packet = build_packet(
        case_id="fixture_case",
        expected_true_total=4,
        motion_windows_path=motion,
        diagnostic_path=diagnostic,
        viability_path=viability,
    )

    assert packet["schema_version"] == "factory-vision-failed-blind-run-learning-packet-v1"
    assert len(packet["truth_review_slots"]) == 4
    assert len(packet["false_positive_candidates"]) == 1
    assert packet["false_positive_candidates"][0]["nearest_motion_window"]["event_id"] == "motion-b"
    assert packet["false_positive_candidates"][0]["sheet_path"] == "sheet-b.jpg"
    assert packet["authority_boundary"]["validation_truth_eligible"] is False
    assert packet["authority_boundary"]["training_eligible"] is False


def test_failed_blind_packet_html_states_review_boundary(tmp_path: Path) -> None:
    packet = {
        "case_id": "fixture_case",
        "expected_true_total": 4,
        "false_positive_candidates": [
            {
                "candidate_id": "hard-negative-1",
                "candidate_type": "runtime_false_positive_candidate",
                "event_ts": 12.0,
                "track_id": 3,
                "travel_px": 1.0,
                "sheet_path": None,
                "clip_path": None,
            }
        ],
        "motion_window_candidates": [],
    }

    html_text = build_html(packet, output_path=tmp_path / "packet.html")

    assert "Failed Blind Run Learning Review" in html_text
    assert "not validation truth" in html_text
    assert "not training eligible" in html_text
    assert "hard-negative-1" in html_text
