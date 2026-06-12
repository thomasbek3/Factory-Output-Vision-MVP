from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


SCHEMA_VERSION = "factory-vision-teacher-labels-v1"
PROMPT_VERSION = "teacher-verification-contract-v2"
ALLOWED_VERIFICATION_DECISIONS = {"assert_completed", "refute_completed", "unclear"}
DECISION_TO_STATUS = {
    "assert_completed": "completed",
    "refute_completed": "worker_only",
    "unclear": "unclear",
}


class TeacherVerificationProvider(Protocol):
    def provider_metadata(self) -> dict[str, Any]:
        ...

    def verify_packet(self, *, packet: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DryRunVerificationProvider:
    name: str = "dry_run_verifier"

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "local_fixture",
            "model": "local-placeholder",
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def verify_packet(self, *, packet: dict[str, Any]) -> dict[str, Any]:
        return _base_verification_label(
            packet=packet,
            suffix="dry-run-verification",
            verification_decision="unclear",
            confidence_tier="low",
            rationale="Dry-run verifier only. No visual model inspected the packet.",
        )


@dataclass(frozen=True)
class FakeVerificationProvider:
    decisions_by_packet_id: dict[str, str] = field(default_factory=dict)
    name: str = "fake_verifier"

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "fake_local_test",
            "model": "fake-verification-provider",
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def verify_packet(self, *, packet: dict[str, Any]) -> dict[str, Any]:
        packet_id = str(packet["packet_id"])
        decision = self.decisions_by_packet_id.get(packet_id, "unclear")
        if decision not in ALLOWED_VERIFICATION_DECISIONS:
            decision = "unclear"
        confidence = "high" if decision == "assert_completed" else "medium" if decision == "refute_completed" else "low"
        return _base_verification_label(
            packet=packet,
            suffix="fake-verification",
            verification_decision=decision,
            confidence_tier=confidence,
            rationale="Fake verifier output for contract tests. No visual model was called.",
        )


@dataclass(frozen=True)
class PendingCloudVerificationProvider:
    name: str
    model: str | None = None
    allow_cloud: bool = False

    def __post_init__(self) -> None:
        if not self.allow_cloud:
            raise ValueError("cloud teacher verification providers are disabled by default")

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "cloud_contract_not_implemented",
            "model": self.model,
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "network_calls_made": False,
        }

    def verify_packet(self, *, packet: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("cloud teacher verification contract exists but no cloud call is implemented")


def verification_provider_for_name(
    name: str,
    *,
    allow_cloud: bool = False,
    model: str | None = None,
    batch_size: int | None = None,
) -> TeacherVerificationProvider:
    normalized = name.strip().lower()
    if normalized in {"dry_run_verifier", "dry_run_fixture", "local_fixture"}:
        return DryRunVerificationProvider(name=normalized)
    if normalized == "fake_verifier":
        return FakeVerificationProvider()
    if normalized in {"claude_cli", "codex_cli"}:
        from app.services.cloud_teacher_providers import (
            ClaudeCliTeacherVerificationProvider,
            CodexCliTeacherVerificationProvider,
        )

        provider_cls = ClaudeCliTeacherVerificationProvider if normalized == "claude_cli" else CodexCliTeacherVerificationProvider
        kwargs: dict[str, Any] = {"allow_cloud": allow_cloud, "model": model}
        if batch_size is not None:
            kwargs["batch_size"] = batch_size
        return provider_cls(**kwargs)
    if normalized in {"openai", "cosmos", "frontier_vlm", "cloud_teacher"}:
        return PendingCloudVerificationProvider(name=normalized, model=model, allow_cloud=allow_cloud)
    raise ValueError(f"unknown teacher verification provider: {name}")


def build_teacher_verifications_from_packets(
    *,
    packet_manifest_path: Path,
    provider: TeacherVerificationProvider,
    max_packets: int | None = None,
    resume_labels: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    packet_manifest = json.loads(packet_manifest_path.read_text(encoding="utf-8"))
    packets = [_load_packet_summary(packet) for packet in packet_manifest.get("packets") or []]
    if max_packets is not None:
        packets = packets[: max(0, int(max_packets))]
    station_id = str(packet_manifest.get("station_id") or "unknown")
    resume_labels = resume_labels or {}
    pending_packets = [packet for packet in packets if str(packet["packet_id"]) not in resume_labels]
    verify_packets = getattr(provider, "verify_packets", None)
    if callable(verify_packets):
        fresh_labels = verify_packets(packets=pending_packets)
    else:
        fresh_labels = [provider.verify_packet(packet=packet) for packet in pending_packets]
    fresh_by_packet_id = {str(label["packet_id"]): label for label in fresh_labels}
    labels = [
        resume_labels.get(str(packet["packet_id"])) or fresh_by_packet_id[str(packet["packet_id"])]
        for packet in packets
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": f"teacher-verification:{station_id}",
        "station_id": station_id,
        "created_at": time.time(),
        "source_evidence_path": str(packet_manifest_path),
        "source_evidence_schema_version": packet_manifest.get("schema_version"),
        "privacy_mode": packet_manifest.get("privacy_mode", "offline_local"),
        "provider": provider.provider_metadata(),
        "prompt_version": PROMPT_VERSION,
        "teacher_task": "verify_candidate_event",
        "refuses_validation_truth": True,
        "labels": labels,
    }


def write_teacher_verifications(path: Path, payload: dict[str, Any], *, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_packet_summary(packet_row: dict[str, Any]) -> dict[str, Any]:
    manifest_path = Path(str(packet_row["packet_manifest_path"]))
    packet = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet["packet_manifest_path"] = str(manifest_path)
    return packet


def build_base_verification_label(
    *,
    packet: dict[str, Any],
    suffix: str,
    verification_decision: str,
    confidence_tier: str,
    rationale: str,
    suggested_event_ts_sec_override: float | None = None,
    duplicate_risk: str = "unknown",
    miss_risk: str = "unknown",
) -> dict[str, Any]:
    if verification_decision not in ALLOWED_VERIFICATION_DECISIONS:
        verification_decision = "unclear"
    packet_id = str(packet["packet_id"])
    window = packet.get("window") or {}
    suggested_event_ts_sec = _event_timestamp_for_decision(verification_decision, window)
    if verification_decision == "assert_completed" and suggested_event_ts_sec_override is not None:
        suggested_event_ts_sec = round(float(suggested_event_ts_sec_override), 3)
    return {
        "label_id": f"{packet_id}-{suffix}",
        "packet_id": packet_id,
        "window_id": packet.get("window_id") or packet_id,
        "candidate_id": packet.get("candidate_id"),
        "source_packet_manifest_path": packet.get("packet_manifest_path"),
        "teacher_output_status": DECISION_TO_STATUS[verification_decision],
        "verification_decision": verification_decision,
        "suggested_event_ts_sec": suggested_event_ts_sec,
        "confidence_tier": confidence_tier,
        "duplicate_risk": duplicate_risk,
        "miss_risk": miss_risk,
        "rationale": rationale,
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
    }


# Backwards-compatible alias for existing in-repo callers.
_base_verification_label = build_base_verification_label


def _event_timestamp_for_decision(verification_decision: str, window: dict[str, Any]) -> float | None:
    if verification_decision != "assert_completed":
        return None
    value = window.get("center_offset_sec")
    return round(float(value), 3) if value is not None else None
