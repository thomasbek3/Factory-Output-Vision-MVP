from __future__ import annotations

import os


ONBOARDING_DASHBOARD_STATES = {"onboarding", "live", "audit", "needs_review"}


def get_onboarding_dashboard_state(*, worker_state: str, source_kind: str) -> str:
    explicit = os.getenv("FC_ONBOARDING_STATE", "").strip().lower().replace("-", "_")
    if explicit in ONBOARDING_DASHBOARD_STATES:
        return explicit
    if worker_state in {"NOT_CONFIGURED", "CALIBRATING", "IDLE"}:
        return "onboarding"
    if worker_state in {"RUNNING_YELLOW_DROP", "RUNNING_YELLOW_RECONNECTING", "RUNNING_RED_STOPPED"}:
        return "needs_review"
    if source_kind == "demo":
        return "onboarding"
    return "live"
