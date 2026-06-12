from __future__ import annotations

import os

from app.services.dashboard_state import get_onboarding_dashboard_state


def test_dashboard_state_defaults_to_onboarding_for_setup_states() -> None:
    assert get_onboarding_dashboard_state(worker_state="NOT_CONFIGURED", source_kind="camera") == "onboarding"
    assert get_onboarding_dashboard_state(worker_state="CALIBRATING", source_kind="camera") == "onboarding"


def test_dashboard_state_defaults_to_live_for_camera_running() -> None:
    assert get_onboarding_dashboard_state(worker_state="RUNNING_GREEN", source_kind="camera") == "live"


def test_dashboard_state_defaults_to_needs_review_for_problem_states() -> None:
    assert get_onboarding_dashboard_state(worker_state="RUNNING_RED_STOPPED", source_kind="camera") == "needs_review"


def test_dashboard_state_allows_explicit_audit_override() -> None:
    previous = os.environ.get("FC_ONBOARDING_STATE")
    os.environ["FC_ONBOARDING_STATE"] = "audit"
    try:
        assert get_onboarding_dashboard_state(worker_state="RUNNING_GREEN", source_kind="camera") == "audit"
    finally:
        if previous is None:
            os.environ.pop("FC_ONBOARDING_STATE", None)
        else:
            os.environ["FC_ONBOARDING_STATE"] = previous
