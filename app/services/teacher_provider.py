from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


SCHEMA_VERSION = "factory-vision-teacher-labels-v1"
PROMPT_VERSION = "onboarding-teacher-contract-v1"
ALLOWED_STATUSES = {"countable", "completed", "in_transit", "static_stack", "worker_only", "unclear"}


class TeacherProvider(Protocol):
    def provider_metadata(self) -> dict[str, Any]:
        ...

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DryRunTeacherProvider:
    name: str = "dry_run_fixture"

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "local_fixture",
            "model": "local-placeholder",
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        return _base_label(
            window=window,
            suffix="teacher-dry-run",
            teacher_output_status="unclear",
            confidence_tier="low",
            rationale="Dry-run placeholder only. No visual model was called.",
        )


@dataclass(frozen=True)
class FakeTeacherProvider:
    statuses_by_window_id: dict[str, str] = field(default_factory=dict)
    name: str = "fake_teacher"

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "fake_local_test",
            "model": "fake-contract-provider",
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        window_id = str(window["window_id"])
        status = self.statuses_by_window_id.get(window_id, "unclear")
        if status not in ALLOWED_STATUSES:
            status = "unclear"
        confidence = "high" if status in {"countable", "completed"} else "low"
        return _base_label(
            window=window,
            suffix="teacher-fake",
            teacher_output_status=status,
            confidence_tier=confidence,
            rationale="Fake local teacher output for contract tests. No visual model was called.",
        )


@dataclass(frozen=True)
class PendingCloudTeacherProvider:
    name: str
    model: str | None = None
    allow_cloud: bool = False

    def __post_init__(self) -> None:
        if not self.allow_cloud:
            raise ValueError("cloud teacher providers are disabled by default")

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "cloud_contract_not_implemented",
            "model": self.model,
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def generate_label(self, *, window: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("cloud teacher provider contract exists but no cloud call is implemented")


def provider_for_name(name: str, *, allow_cloud: bool = False) -> TeacherProvider:
    normalized = name.strip().lower()
    if normalized in {"dry_run_fixture", "local_fixture"}:
        return DryRunTeacherProvider(name=normalized)
    if normalized == "fake_teacher":
        return FakeTeacherProvider()
    if normalized in {"openai", "cosmos", "frontier_vlm", "cloud_teacher"}:
        return PendingCloudTeacherProvider(name=normalized, allow_cloud=allow_cloud)
    raise ValueError(f"unknown teacher provider: {name}")


def build_teacher_labels_from_windows(*, window_manifest_path: Path, provider: TeacherProvider) -> dict[str, Any]:
    window_manifest = json.loads(window_manifest_path.read_text(encoding="utf-8"))
    windows = list(window_manifest.get("windows") or [])
    station_id = str(window_manifest["station_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": f"onboarding:{station_id}",
        "station_id": station_id,
        "created_at": time.time(),
        "source_evidence_path": str(window_manifest_path),
        "privacy_mode": "offline_local",
        "provider": provider.provider_metadata(),
        "refuses_validation_truth": True,
        "labels": [provider.generate_label(window=window) for window in windows],
    }


def write_teacher_labels(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_label(
    *,
    window: dict[str, Any],
    suffix: str,
    teacher_output_status: str,
    confidence_tier: str,
    rationale: str,
) -> dict[str, Any]:
    window_id = str(window["window_id"])
    return {
        "label_id": f"{window_id}-{suffix}",
        "window_id": window_id,
        "teacher_output_status": teacher_output_status,
        "suggested_event_ts_sec": _window_center(window),
        "confidence_tier": confidence_tier,
        "duplicate_risk": "unknown",
        "miss_risk": "unknown",
        "rationale": rationale,
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


def _window_center(window: dict[str, Any]) -> float | None:
    start = window.get("start_offset_sec")
    duration = window.get("duration_sec")
    if start is None or duration is None:
        return None
    return round(float(start) + (float(duration) / 2.0), 3)
