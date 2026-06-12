from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.services.teacher_verification import (
    ALLOWED_VERIFICATION_DECISIONS,
    build_base_verification_label,
)

CLI_PROMPT_VERSION = "teacher-verification-cli-v1"
PRIMARY_SEQUENCE_KIND = "output_zone_crop_sequence"
FULL_FRAME_CAPTIONS = (
    ("before_full_frame", "BEFORE full frame"),
    ("during_full_frame", "DURING full frame"),
    ("after_full_frame", "AFTER full frame"),
    ("frame_diff_or_motion_heatmap", "BEFORE/AFTER diff heatmap"),
)
ALLOWED_RISK_TIERS = {"low", "medium", "high", "unknown"}
ALLOWED_CONFIDENCE_TIERS = {"high", "medium", "low", "unknown"}

SYSTEM_CONTRACT = """You are a manufacturing vision teacher reviewing evidence packets from a fixed factory camera.
Each packet covers one candidate event window. For each packet answer exactly one question:
did this window show ONE completed countable output placement (a finished part coming to rest
in the output stack/zone)?

Decision contract per packet:
- "assert_completed": the evidence shows, or strongly implies, that the output stack gained one
  part during this window. Assert when before-vs-after evidence or the frame sequence shows the
  stack changing, EVEN IF the exact placement instant is occluded by the worker's hands or body.
  Workers almost always occlude the placement moment; occlusion is NOT a reason to withhold an
  assert when the before and after states clearly differ.
- "refute_completed": the window clearly shows no completed placement (worker activity only,
  part still in transit at window end, or a static stack with no change).
- "unclear": the evidence is genuinely unusable or contradictory (corrupted frames, wrong camera
  region). Use this sparingly.

Calibration - read carefully: this pipeline is asymmetric by design. Your assertion is NOT the
final word. A separate, conservative state-diff reconciler independently verifies every assert
before anything is promoted, so an optimistic false assert is cheap, while a missed real event
is expensive and unrecoverable. You are the high-recall stage. If the evidence is consistent
with a completed placement and you judge the probability to be at least about 60 percent, choose
"assert_completed" and express your remaining doubt through confidence_tier ("medium" or "low"),
not by switching to "unclear" or "refute_completed".

Timing: if you assert, set suggested_event_ts_sec to the timestamp in seconds - matching the
"t=" labels on the evidence images - where the placement most plausibly completed (the first
frame where the new part is at rest). An error of two to three seconds is acceptable.

duplicate_risk: likelihood this same physical placement is also covered by an adjacent packet
(for example the event sits at the very edge of this window). miss_risk: likelihood the window
contains an ADDITIONAL placement beyond the one you are judging.
"""


@dataclass
class CliTeacherUsage:
    invocations: int = 0
    packets_labeled: int = 0
    parse_failures: int = 0
    transport_errors: int = 0
    retries: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "invocations": self.invocations,
            "packets_labeled": self.packets_labeled,
            "parse_failures": self.parse_failures,
            "transport_errors": self.transport_errors,
            "retries": self.retries,
        }


@dataclass(frozen=True)
class CliTeacherRequest:
    prompt: str
    image_paths: tuple[str, ...]
    model: str | None
    timeout_sec: float


CliTransport = Callable[[CliTeacherRequest], str]


@dataclass
class _CliTeacherVerificationProvider:
    name: str = "cli_teacher"
    model: str | None = None
    allow_cloud: bool = False
    batch_size: int = 4
    max_sequence_images: int = 8
    max_images_per_packet: int = 12
    timeout_sec: float = 900.0
    image_reference_mode: str = "read_tool_paths"  # or "attached_in_order"
    transport: CliTransport | None = None
    usage: CliTeacherUsage = field(default_factory=CliTeacherUsage)

    def __post_init__(self) -> None:
        if not self.allow_cloud:
            raise ValueError("cloud teacher verification providers are disabled by default")

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": "subscription_cli",
            "model": self.model or "cli_default",
            "model_revision": None,
            "prompt_version": CLI_PROMPT_VERSION,
            "network_calls_made": self.usage.invocations > 0,
            "usage": self.usage.as_dict(),
        }

    def verify_packet(self, *, packet: dict[str, Any]) -> dict[str, Any]:
        return self.verify_packets(packets=[packet])[0]

    def verify_packets(self, *, packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        labels: list[dict[str, Any]] = []
        batch_size = max(1, int(self.batch_size))
        for start in range(0, len(packets), batch_size):
            labels.extend(self._verify_batch(packets[start : start + batch_size]))
        return labels

    def _verify_batch(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entries = [(packet, select_packet_images(packet, max_sequence_images=self.max_sequence_images, max_images=self.max_images_per_packet)) for packet in batch]
        prompt = build_batch_prompt(entries, image_reference_mode=self.image_reference_mode)
        image_paths = tuple(path for _, images in entries for path, _ in images)
        request = CliTeacherRequest(prompt=prompt, image_paths=image_paths, model=self.model, timeout_sec=self.timeout_sec)

        raw_text: str | None = None
        failure_reason: str | None = None
        try:
            raw_text = self._run_transport(request)
            self.usage.invocations += 1
        except Exception as exc:  # noqa: BLE001 - any transport failure becomes unclear labels, never a crash
            self.usage.transport_errors += 1
            failure_reason = f"provider_error: transport {type(exc).__name__}"

        parsed_by_id: dict[str, dict[str, Any]] = {}
        if raw_text is not None:
            parsed = parse_batch_response(raw_text)
            if parsed is None:
                self.usage.parse_failures += 1
                failure_reason = "provider_error: unparseable teacher response"
            else:
                parsed_by_id = parsed

        missing = [packet for packet in batch if str(packet["packet_id"]) not in parsed_by_id]
        if missing and len(batch) > 1 and failure_reason is None:
            failure_reason = "provider_error: packet missing from batch response"
        if failure_reason is not None and len(batch) > 1:
            self.usage.retries += 1
            midpoint = len(batch) // 2
            return self._verify_batch(batch[:midpoint]) + self._verify_batch(batch[midpoint:])

        labels = []
        for packet in batch:
            packet_id = str(packet["packet_id"])
            entry = parsed_by_id.get(packet_id)
            if entry is None:
                labels.append(self._unclear_label(packet, failure_reason or "provider_error: packet missing from batch response"))
            else:
                labels.append(self._label_from_entry(packet, entry))
            self.usage.packets_labeled += 1
        return labels

    def _run_transport(self, request: CliTeacherRequest) -> str:
        transport = self.transport or self._default_transport()
        return transport(request)

    def _default_transport(self) -> CliTransport:
        raise NotImplementedError("base CLI provider has no default transport")

    def _unclear_label(self, packet: dict[str, Any], rationale: str) -> dict[str, Any]:
        return build_base_verification_label(
            packet=packet,
            suffix=f"{self.name}-verification",
            verification_decision="unclear",
            confidence_tier="low",
            rationale=rationale,
        )

    def _label_from_entry(self, packet: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        decision = str(entry.get("verification_decision") or "").strip().lower()
        if decision not in ALLOWED_VERIFICATION_DECISIONS:
            decision = "unclear"
        window = packet.get("window") or {}
        suggested = _clamped_timestamp(entry.get("suggested_event_ts_sec"), window) if decision == "assert_completed" else None
        return build_base_verification_label(
            packet=packet,
            suffix=f"{self.name}-verification",
            verification_decision=decision,
            confidence_tier=_normalized_tier(entry.get("confidence_tier"), ALLOWED_CONFIDENCE_TIERS),
            rationale=str(entry.get("rationale") or "").strip() or "teacher returned no rationale",
            suggested_event_ts_sec_override=suggested,
            duplicate_risk=_normalized_tier(entry.get("duplicate_risk"), ALLOWED_RISK_TIERS),
            miss_risk=_normalized_tier(entry.get("miss_risk"), ALLOWED_RISK_TIERS),
        )


@dataclass
class ClaudeCliTeacherVerificationProvider(_CliTeacherVerificationProvider):
    name: str = "claude_cli"
    image_reference_mode: str = "read_tool_paths"

    def _default_transport(self) -> CliTransport:
        return run_claude_cli


@dataclass
class CodexCliTeacherVerificationProvider(_CliTeacherVerificationProvider):
    name: str = "codex_cli"
    image_reference_mode: str = "attached_in_order"

    def _default_transport(self) -> CliTransport:
        return run_codex_cli


def select_packet_images(
    packet: dict[str, Any],
    *,
    max_sequence_images: int = 8,
    max_images: int = 12,
) -> list[tuple[str, str]]:
    """Deterministic (path, caption) selection from a packet manifest's assets."""
    assets = packet.get("assets") or []
    selected: list[tuple[str, str]] = []
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        by_kind.setdefault(str(asset.get("kind")), []).append(asset)

    for kind, caption in FULL_FRAME_CAPTIONS:
        for asset in by_kind.get(kind, [])[:1]:
            path = str(asset.get("path") or "")
            if path and Path(path).exists():
                selected.append((path, _captioned(caption, asset.get("timestamp_sec"))))

    sequence = sorted(
        (asset for asset in by_kind.get(PRIMARY_SEQUENCE_KIND, []) if asset.get("path") and Path(str(asset["path"])).exists()),
        key=lambda row: (float(row.get("timestamp_sec") or 0.0), str(row.get("path"))),
    )
    for index, asset in enumerate(_evenly_subsample(sequence, max_sequence_images)):
        caption = f"SEQUENCE frame {index + 1}"
        selected.append((str(asset["path"]), _captioned(caption, asset.get("timestamp_sec"))))

    return selected[: max(1, int(max_images))]


def build_batch_prompt(
    entries: list[tuple[dict[str, Any], list[tuple[str, str]]]],
    *,
    image_reference_mode: str,
) -> str:
    lines: list[str] = [SYSTEM_CONTRACT.strip(), ""]
    if image_reference_mode == "read_tool_paths":
        lines.append("Use the Read tool to view every evidence image listed below before deciding.")
    else:
        lines.append("The evidence images are attached to this message in the exact order listed below.")
    lines.append("")

    image_counter = 0
    for packet, images in entries:
        window = packet.get("window") or {}
        lines.append(
            "PACKET {pid} (station {station}, window start={start}s center={center}s end={end}s):".format(
                pid=packet.get("packet_id"),
                station=packet.get("station_id"),
                start=window.get("start_offset_sec"),
                center=window.get("center_offset_sec"),
                end=window.get("end_offset_sec"),
            )
        )
        if not images:
            lines.append("- no evidence images available for this packet; answer unclear for it")
        for path, caption in images:
            image_counter += 1
            if image_reference_mode == "read_tool_paths":
                lines.append(f"- {caption}: {path}")
            else:
                lines.append(f"- Image {image_counter}: {caption}")
        lines.append("")

    lines.append(
        "Respond with ONLY a JSON array and no other text, one object per packet, in the same order:"
    )
    lines.append(
        '[{"packet_id": "<id>", "verification_decision": "assert_completed" | "refute_completed" | "unclear", '
        '"suggested_event_ts_sec": <number or null>, "confidence_tier": "high" | "medium" | "low", '
        '"duplicate_risk": "low" | "medium" | "high", "miss_risk": "low" | "medium" | "high", '
        '"rationale": "<one or two sentences citing specific frames or timestamps>"}]'
    )
    return "\n".join(lines)


def parse_batch_response(text: str) -> dict[str, dict[str, Any]] | None:
    """Lenient parse: first JSON array (or single object) in the text, keyed by packet_id."""
    candidate = _extract_json_payload(text)
    if candidate is None:
        return None
    if isinstance(candidate, dict):
        candidate = [candidate]
    if not isinstance(candidate, list):
        return None
    parsed: dict[str, dict[str, Any]] = {}
    for entry in candidate:
        if isinstance(entry, dict) and entry.get("packet_id"):
            parsed[str(entry["packet_id"])] = entry
    return parsed or None


def run_claude_cli(request: CliTeacherRequest) -> str:
    command = [
        "claude",
        "-p",
        request.prompt,
        "--output-format",
        "json",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--setting-sources",
        "",
    ]
    if request.model:
        command.extend(["--model", request.model])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=request.timeout_sec,
        cwd=_neutral_cwd(request.image_paths),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"claude cli exited {completed.returncode}: {completed.stderr.strip()[:400]}")
    try:
        envelope = json.loads(completed.stdout)
        result = envelope.get("result")
        if isinstance(result, str) and result.strip():
            return result
    except (json.JSONDecodeError, AttributeError):
        pass
    return completed.stdout


def run_codex_cli(request: CliTeacherRequest) -> str:
    with tempfile.TemporaryDirectory(prefix="factory-codex-teacher-") as tmp:
        out_file = Path(tmp) / "last_message.txt"
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-s",
            "read-only",
            "--color",
            "never",
            "-o",
            str(out_file),
        ]
        if request.model:
            command.extend(["-m", request.model])
        for image_path in request.image_paths:
            command.extend(["-i", image_path])
        # "-i" is variadic, so the prompt is passed via stdin ("-") to avoid being consumed as an image path.
        command.append("-")
        completed = subprocess.run(
            command,
            input=request.prompt,
            capture_output=True,
            text=True,
            timeout=request.timeout_sec,
            cwd=_neutral_cwd(request.image_paths),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"codex cli exited {completed.returncode}: {completed.stderr.strip()[:400]}")
        if out_file.exists():
            text = out_file.read_text(encoding="utf-8")
            if text.strip():
                return text
        return completed.stdout


def _captioned(caption: str, timestamp_sec: Any) -> str:
    if timestamp_sec is None:
        return caption
    return f"{caption} (t={round(float(timestamp_sec), 3)}s)"


def _evenly_subsample(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    if limit == 1:
        return [rows[len(rows) // 2]]
    indices = sorted({round(index * (len(rows) - 1) / (limit - 1)) for index in range(limit)})
    return [rows[index] for index in indices]


def _extract_json_payload(text: str) -> Any | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    for candidate in (stripped, _bracket_slice(stripped, "[", "]"), _bracket_slice(stripped, "{", "}")):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _bracket_slice(text: str, open_char: str, close_char: str) -> str | None:
    start = text.find(open_char)
    end = text.rfind(close_char)
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalized_tier(value: Any, allowed: set[str]) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else "unknown"


def _clamped_timestamp(value: Any, window: dict[str, Any]) -> float | None:
    if value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    start = window.get("start_offset_sec")
    end = window.get("end_offset_sec")
    if start is not None:
        timestamp = max(timestamp, float(start))
    if end is not None:
        timestamp = min(timestamp, float(end))
    return round(timestamp, 3)


def _neutral_cwd(image_paths: tuple[str, ...]) -> str:
    """Run CLIs from the evidence directory, not the repo, to avoid loading repo agent context."""
    for image_path in image_paths:
        parent = Path(image_path).parent
        if parent.is_dir():
            return str(parent)
    return tempfile.gettempdir()
