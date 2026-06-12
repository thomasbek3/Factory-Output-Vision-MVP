from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "factory-vision-onboarding-session-v1"

CREATED = "created"
RECORDING = "recording"
SEGMENTS_READY = "segments_ready"
WINDOWS_READY = "windows_ready"
TEACHER_PENDING = "teacher_pending"
TEACHER_READY = "teacher_ready"
CALIBRATION_READY = "calibration_ready"
TRAINING_READY = "training_ready"
READY_FOR_BLIND_REPLAY = "ready_for_blind_replay"
READY_FOR_LIVE = "ready_for_live"
LIVE = "live"
NEEDS_REVIEW = "needs_review"
BLOCKED = "blocked"

FAIL_CLOSED_STATES = {NEEDS_REVIEW, BLOCKED}
LIVE_STATES = {READY_FOR_LIVE, LIVE}


@dataclass
class OnboardingSession:
    session_id: str
    station_id: str
    state: str = CREATED
    dry_run: bool = True
    cloud_allowed: bool = False
    artifacts: dict[str, str] = field(default_factory=dict)
    failure_reason: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @property
    def ready_for_live(self) -> bool:
        return self.state in LIVE_STATES

    @property
    def failed_closed(self) -> bool:
        return self.state in FAIL_CLOSED_STATES and not self.ready_for_live


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def start_onboarding_session(
    *, station_id: str, session_id: str | None = None, dry_run: bool = True, cloud_allowed: bool = False
) -> OnboardingSession:
    session = OnboardingSession(
        session_id=session_id or uuid.uuid4().hex,
        station_id=station_id,
        dry_run=bool(dry_run),
        cloud_allowed=bool(cloud_allowed),
    )
    _append_history(session, event="create", state_from=None, state_to=CREATED)
    return session


def apply_onboarding_event(
    session: OnboardingSession,
    event: str,
    *,
    artifact_path: str | None = None,
    reason: str | None = None,
) -> OnboardingSession:
    state_from = session.state
    if session.state in {LIVE, NEEDS_REVIEW, BLOCKED}:
        _append_history(
            session,
            event=event,
            state_from=state_from,
            state_to=session.state,
            reason=reason or "terminal_state",
        )
        return session

    if event == "recording_started" and session.state == CREATED:
        return _transition(session, event=event, state_from=state_from, state_to=RECORDING)
    if event == "segments_available" and session.state in {CREATED, RECORDING}:
        _require_artifact(event, artifact_path)
        session.artifacts["segment_manifest"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=SEGMENTS_READY)
    if event == "windows_extracted" and session.state == SEGMENTS_READY:
        _require_artifact(event, artifact_path)
        session.artifacts["window_manifest"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=WINDOWS_READY)
    if event == "teacher_requested" and session.state == WINDOWS_READY:
        return _transition(session, event=event, state_from=state_from, state_to=TEACHER_PENDING)
    if event == "teacher_completed" and session.state == TEACHER_PENDING:
        _require_artifact(event, artifact_path)
        if session.dry_run:
            return _fail_closed(session, event=event, state_from=state_from, reason="dry_run_teacher_cannot_unlock_live")
        session.artifacts["teacher_labels"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=TEACHER_READY)
    if event == "teacher_unavailable" and session.state in {WINDOWS_READY, TEACHER_PENDING}:
        return _fail_closed(session, event=event, state_from=state_from, reason=reason or "teacher_provider_required")
    if event == "calibration_ready" and session.state == TEACHER_READY:
        _require_artifact(event, artifact_path)
        session.artifacts["station_calibration"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=CALIBRATION_READY)
    if event == "training_ready" and session.state == CALIBRATION_READY:
        _require_artifact(event, artifact_path)
        session.artifacts["training_report"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=TRAINING_READY)
    if event == "blind_replay_ready" and session.state == TRAINING_READY:
        return _transition(session, event=event, state_from=state_from, state_to=READY_FOR_BLIND_REPLAY)
    if event == "blind_replay_passed" and session.state == READY_FOR_BLIND_REPLAY:
        _require_artifact(event, artifact_path)
        session.artifacts["blind_replay_report"] = artifact_path
        return _transition(session, event=event, state_from=state_from, state_to=READY_FOR_LIVE)
    if event == "activate_live" and session.state == READY_FOR_LIVE:
        return _transition(session, event=event, state_from=state_from, state_to=LIVE)

    return _fail_closed(session, event=event, state_from=state_from, reason=reason or f"invalid_transition:{state_from}:{event}")


def run_dry_run_onboarding_session(
    *, station_id: str, segment_manifest_path: str, window_manifest_path: str
) -> OnboardingSession:
    session = start_onboarding_session(station_id=station_id, dry_run=True, cloud_allowed=False)
    apply_onboarding_event(session, "recording_started")
    apply_onboarding_event(session, "segments_available", artifact_path=segment_manifest_path)
    apply_onboarding_event(session, "windows_extracted", artifact_path=window_manifest_path)
    apply_onboarding_event(session, "teacher_requested")
    apply_onboarding_event(session, "teacher_unavailable", reason="dry_run_no_teacher_provider")
    return session


def write_onboarding_session(session: OnboardingSession, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(session), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_onboarding_session(path: Path) -> OnboardingSession:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported onboarding session schema: {payload.get('schema_version')}")
    return OnboardingSession(**payload)


def _transition(
    session: OnboardingSession,
    *,
    event: str,
    state_from: str | None,
    state_to: str,
    reason: str | None = None,
) -> OnboardingSession:
    session.state = state_to
    session.failure_reason = reason if state_to in FAIL_CLOSED_STATES else None
    _append_history(session, event=event, state_from=state_from, state_to=state_to, reason=reason)
    return session


def _fail_closed(session: OnboardingSession, *, event: str, state_from: str, reason: str) -> OnboardingSession:
    return _transition(session, event=event, state_from=state_from, state_to=NEEDS_REVIEW, reason=reason)


def _append_history(
    session: OnboardingSession,
    *,
    event: str,
    state_from: str | None,
    state_to: str,
    reason: str | None = None,
) -> None:
    session.history.append(
        {
            "event": event,
            "state_from": state_from,
            "state_to": state_to,
            "reason": reason,
            "created_at": utc_now_iso(),
        }
    )


def _require_artifact(event: str, artifact_path: str | None) -> None:
    if not artifact_path:
        raise ValueError(f"{event} requires artifact_path")
