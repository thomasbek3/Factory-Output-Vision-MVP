#!/usr/bin/env python3
"""Audit extracted event windows with dry-run or local Moondream Station providers."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


SCHEMA_VERSION = "factory-vision-teacher-labels-v1"
PROMPT_VERSION = "moondream-event-audit-v1"
ALLOWED_STATUSES = {"countable", "completed", "in_transit", "static_stack", "worker_only", "unclear"}
ALLOWED_RISKS = {"high", "medium", "low", "unknown"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _local_endpoint(endpoint: str) -> bool:
    parsed = urllib.parse.urlparse(endpoint)
    return parsed.hostname in LOCAL_HOSTS


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _normalized_status(value: Any) -> str:
    status = str(value or "unclear").strip().lower()
    return status if status in ALLOWED_STATUSES else "unclear"


def _normalized_risk(value: Any) -> str:
    risk = str(value or "unknown").strip().lower()
    risk = {
        "confident": "high",
        "very confident": "high",
        "yes": "high",
        "true": "high",
        "present": "high",
        "moderate": "medium",
        "maybe": "medium",
        "no": "low",
        "false": "low",
        "none": "low",
        "absent": "low",
    }.get(risk, risk)
    return risk if risk in ALLOWED_RISKS else "unknown"


def _uncertain_rationale(text: str) -> bool:
    normalized = text.strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "cannot be determined",
            "can't be determined",
            "unable to determine",
            "not enough information",
            "cannot determine",
        )
    )


def _best_written_frame_asset(window: dict[str, Any]) -> dict[str, Any] | None:
    assets = ((window.get("review_window") or {}).get("frame_assets") or [])
    center_sec = (window.get("time_window") or {}).get("center_sec")
    written_assets = [
        asset
        for asset in assets
        if asset.get("status") == "written" and asset.get("frame_path")
    ]
    if center_sec is not None and written_assets:
        return min(
            written_assets,
            key=lambda asset: abs(float(asset.get("timestamp_sec") or 0.0) - float(center_sec)),
        )
    for asset in assets:
        if asset.get("status") == "written" and asset.get("frame_path"):
            return asset
    return None


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_moondream_question(window: dict[str, Any]) -> str:
    time_window = window.get("time_window") or {}
    return (
        "You are auditing a Factory Vision event window. "
        "Return JSON only with keys: "
        "teacher_output_status, confidence_tier, duplicate_risk, miss_risk, rationale. "
        "Allowed teacher_output_status values are: countable, completed, in_transit, static_stack, worker_only, unclear. "
        "Allowed confidence_tier values are: high, medium, low, unknown. "
        "Allowed duplicate_risk and miss_risk values are: high, medium, low, unknown. "
        "Base rationale only on visual evidence in the image. "
        "Do not repeat the window metadata as the rationale. "
        "Use unclear instead of guessing. "
        f"Window id: {window.get('window_id')}. "
        f"Window type: {window.get('window_type')}. "
        f"Center timestamp seconds: {time_window.get('center_sec')}."
    )


class AuditProvider(Protocol):
    def provider_metadata(self) -> dict[str, Any]:
        ...

    def audit_window(self, *, window: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DryRunAuditProvider:
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

    def audit_window(self, *, window: dict[str, Any]) -> dict[str, Any]:
        return {
            "teacher_output_status": "unclear",
            "confidence_tier": "low",
            "duplicate_risk": str(window.get("duplicate_risk") or "unknown"),
            "miss_risk": str(window.get("miss_risk") or "unknown"),
            "rationale": "Dry-run Moondream audit placeholder. No model was called.",
            "raw_answer": None,
            "frame_asset": _best_written_frame_asset(window),
        }


@dataclass(frozen=True)
class MoondreamStationProvider:
    endpoint: str = "http://127.0.0.1:2020/v1"
    timeout_sec: float = 30.0
    max_tokens: int = 192
    temperature: float = 0.0
    allow_nonlocal_endpoint: bool = False
    post_json: Callable[[str, dict[str, Any], float], dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if not self.allow_nonlocal_endpoint and not _local_endpoint(self.endpoint):
            raise ValueError("Moondream Station endpoint must be localhost unless allow_nonlocal_endpoint is explicit")

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": "moondream_station",
            "mode": "local_http",
            "model": "moondream-station",
            "model_revision": None,
            "prompt_version": PROMPT_VERSION,
            "endpoint": self.endpoint,
            "network_calls_made": True,
        }

    def audit_window(self, *, window: dict[str, Any]) -> dict[str, Any]:
        asset = _best_written_frame_asset(window)
        if asset is None:
            return {
                "teacher_output_status": "unclear",
                "confidence_tier": "low",
                "duplicate_risk": str(window.get("duplicate_risk") or "unknown"),
                "miss_risk": str(window.get("miss_risk") or "unknown"),
                "rationale": "No extracted review frame was available for Moondream audit.",
                "raw_answer": None,
                "frame_asset": None,
            }
        question = build_moondream_question(window)
        request_payload = {
            "image_url": _image_data_url(Path(str(asset["frame_path"]))),
            "question": question,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        response = self._post_json(f"{self.endpoint.rstrip('/')}/query", request_payload, self.timeout_sec)
        if response.get("error"):
            error = str(response.get("error"))
            return {
                "teacher_output_status": "unclear",
                "confidence_tier": "low",
                "duplicate_risk": str(window.get("duplicate_risk") or "unknown"),
                "miss_risk": str(window.get("miss_risk") or "unknown"),
                "rationale": f"Moondream Station error: {error}",
                "raw_answer": None,
                "provider_error": error,
                "request_id": response.get("request_id"),
                "frame_asset": asset,
            }
        answer = str(response.get("answer") or "")
        parsed = _extract_json_object(answer) or {}
        rationale = str(parsed.get("rationale") or answer or "Moondream returned no rationale.")
        teacher_output_status = _normalized_status(parsed.get("teacher_output_status"))
        confidence_tier = _normalized_risk(parsed.get("confidence_tier"))
        duplicate_risk = _normalized_risk(parsed.get("duplicate_risk"))
        miss_risk = _normalized_risk(parsed.get("miss_risk"))
        if teacher_output_status != "unclear" and _uncertain_rationale(rationale):
            teacher_output_status = "unclear"
            confidence_tier = "low"
            duplicate_risk = "unknown"
            miss_risk = "unknown"
        return {
            "teacher_output_status": teacher_output_status,
            "confidence_tier": confidence_tier,
            "duplicate_risk": duplicate_risk,
            "miss_risk": miss_risk,
            "rationale": rationale,
            "raw_answer": answer,
            "request_id": response.get("request_id"),
            "frame_asset": asset,
        }

    def _post_json(self, url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
        if self.post_json is not None:
            return self.post_json(url, payload, timeout_sec)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:  # noqa: S310 - explicit local endpoint gate.
            return json.loads(response.read().decode("utf-8"))


def provider_for_args(args: argparse.Namespace) -> AuditProvider:
    if args.provider == "dry_run_fixture":
        return DryRunAuditProvider()
    if args.provider == "moondream_station":
        return MoondreamStationProvider(
            endpoint=args.endpoint,
            timeout_sec=args.timeout_sec,
            allow_nonlocal_endpoint=args.allow_nonlocal_endpoint,
        )
    raise ValueError(f"unsupported provider: {args.provider}")


def build_label_from_audit(*, window: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    window_id = str(window["window_id"])
    return {
        "label_id": f"{window_id}-moondream-audit",
        "window_id": window_id,
        "teacher_output_status": _normalized_status(audit.get("teacher_output_status")),
        "suggested_event_ts_sec": (window.get("time_window") or {}).get("center_sec"),
        "confidence_tier": _normalized_risk(audit.get("confidence_tier")),
        "duplicate_risk": _normalized_risk(audit.get("duplicate_risk")),
        "miss_risk": _normalized_risk(audit.get("miss_risk")),
        "rationale": str(audit.get("rationale") or ""),
        "label_authority_tier": "bronze",
        "review_status": "pending",
        "validation_truth_eligible": False,
        "training_eligible": False,
        "audit_metadata": {
            "raw_answer": audit.get("raw_answer"),
            "provider_error": audit.get("provider_error"),
            "request_id": audit.get("request_id"),
            "frame_asset": audit.get("frame_asset"),
        },
    }


def build_moondream_audit_labels(
    *,
    evidence_path: Path,
    provider: AuditProvider,
    max_windows: int | None = None,
) -> dict[str, Any]:
    evidence = read_json(evidence_path)
    windows = list(evidence.get("windows") or [])
    if max_windows is not None:
        windows = windows[:max_windows]
    labels = [
        build_label_from_audit(window=window, audit=provider.audit_window(window=window))
        for window in windows
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": evidence["case_id"],
        "created_at": round(time.time(), 3),
        "source_evidence_path": evidence_path.as_posix(),
        "privacy_mode": evidence.get("privacy_mode", "offline_local"),
        "provider": provider.provider_metadata(),
        "refuses_validation_truth": True,
        "labels": labels,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit active-learning evidence windows with Moondream")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--provider", choices=["dry_run_fixture", "moondream_station"], default="dry_run_fixture")
    parser.add_argument("--endpoint", default="http://127.0.0.1:2020/v1")
    parser.add_argument("--allow-nonlocal-endpoint", action="store_true")
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--max-windows", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    provider = provider_for_args(args)
    payload = build_moondream_audit_labels(
        evidence_path=args.evidence,
        provider=provider,
        max_windows=args.max_windows,
    )
    write_json(args.output, payload, force=args.force)
    print(json.dumps({"output": args.output.as_posix(), "label_count": len(payload["labels"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
