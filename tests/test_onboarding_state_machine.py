from __future__ import annotations

from pathlib import Path

import pytest

from app.services.onboarding_state import (
    LIVE,
    NEEDS_REVIEW,
    READY_FOR_LIVE,
    SEGMENTS_READY,
    TEACHER_PENDING,
    WINDOWS_READY,
    apply_onboarding_event,
    read_onboarding_session,
    run_dry_run_onboarding_session,
    start_onboarding_session,
    write_onboarding_session,
)


def test_dry_run_onboarding_session_moves_through_states_and_fails_closed() -> None:
    session = run_dry_run_onboarding_session(
        station_id="line-a",
        segment_manifest_path="/tmp/segments.json",
        window_manifest_path="/tmp/windows.json",
    )

    states = [row["state_to"] for row in session.history]
    assert states == [
        "created",
        "recording",
        SEGMENTS_READY,
        WINDOWS_READY,
        TEACHER_PENDING,
        NEEDS_REVIEW,
    ]
    assert session.failed_closed is True
    assert session.ready_for_live is False
    assert session.failure_reason == "dry_run_no_teacher_provider"
    assert session.artifacts == {
        "segment_manifest": "/tmp/segments.json",
        "window_manifest": "/tmp/windows.json",
    }


def test_invalid_live_activation_before_blind_replay_fails_closed() -> None:
    session = start_onboarding_session(station_id="line-a", dry_run=False)
    apply_onboarding_event(session, "segments_available", artifact_path="/tmp/segments.json")

    apply_onboarding_event(session, "activate_live")

    assert session.state == NEEDS_REVIEW
    assert session.ready_for_live is False
    assert session.failure_reason == "invalid_transition:segments_ready:activate_live"


def test_non_dry_run_can_reach_live_only_after_required_artifacts() -> None:
    session = start_onboarding_session(station_id="line-a", dry_run=False)
    apply_onboarding_event(session, "segments_available", artifact_path="/tmp/segments.json")
    apply_onboarding_event(session, "windows_extracted", artifact_path="/tmp/windows.json")
    apply_onboarding_event(session, "teacher_requested")
    apply_onboarding_event(session, "teacher_completed", artifact_path="/tmp/teacher.json")
    apply_onboarding_event(session, "calibration_ready", artifact_path="/tmp/station_calibration.json")
    apply_onboarding_event(session, "training_ready", artifact_path="/tmp/training_report.json")
    apply_onboarding_event(session, "blind_replay_ready")
    apply_onboarding_event(session, "blind_replay_passed", artifact_path="/tmp/blind_replay_report.json")

    assert session.state == READY_FOR_LIVE
    assert session.ready_for_live is True

    apply_onboarding_event(session, "activate_live")

    assert session.state == LIVE
    assert session.artifacts["teacher_labels"] == "/tmp/teacher.json"
    assert session.artifacts["station_calibration"] == "/tmp/station_calibration.json"
    assert session.artifacts["blind_replay_report"] == "/tmp/blind_replay_report.json"


def test_dry_run_teacher_completion_cannot_unlock_readiness() -> None:
    session = start_onboarding_session(station_id="line-a", dry_run=True)
    apply_onboarding_event(session, "segments_available", artifact_path="/tmp/segments.json")
    apply_onboarding_event(session, "windows_extracted", artifact_path="/tmp/windows.json")
    apply_onboarding_event(session, "teacher_requested")

    apply_onboarding_event(session, "teacher_completed", artifact_path="/tmp/teacher.json")

    assert session.state == NEEDS_REVIEW
    assert session.failed_closed is True
    assert session.failure_reason == "dry_run_teacher_cannot_unlock_live"


def test_onboarding_session_round_trips_to_json(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    session = run_dry_run_onboarding_session(
        station_id="line-a",
        segment_manifest_path="/tmp/segments.json",
        window_manifest_path="/tmp/windows.json",
    )

    write_onboarding_session(session, path)
    loaded = read_onboarding_session(path)

    assert loaded.session_id == session.session_id
    assert loaded.station_id == "line-a"
    assert loaded.state == NEEDS_REVIEW
    assert loaded.failed_closed is True
    assert loaded.history[-1]["reason"] == "dry_run_no_teacher_provider"


def test_required_artifact_events_fail_fast() -> None:
    session = start_onboarding_session(station_id="line-a")

    with pytest.raises(ValueError, match="artifact_path"):
        apply_onboarding_event(session, "segments_available")
