from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.settings import get_demo_count_cache_path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "reports"
AUDIT_SCHEMA_VERSION = "factory2-runtime-event-audit-v1"


@dataclass(frozen=True)
class DemoReceipt:
    event_ts: float
    track_id: int
    count_authority: str | None
    payload: dict[str, Any]


class DeterministicDemoRunner:
    """Reveal audited runtime receipts against demo playback wall-clock time."""

    def __init__(self, *, cache_path: Path | None = None, report_dir: Path | None = None) -> None:
        self._cache_path = cache_path or get_demo_count_cache_path()
        self._report_dir = report_dir or DEFAULT_REPORT_DIR
        self._report_path: Path | None = None
        self._payload: dict[str, Any] | None = None
        self._receipts: list[DemoReceipt] = []
        self._cursor = 0
        self._playback_speed = 1.0
        self._started_monotonic: float | None = None

    @property
    def report_path(self) -> Path | None:
        return self._report_path

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def revealed_count(self) -> int:
        return self._cursor

    @property
    def expected_final_count(self) -> int:
        if self._payload is None:
            return 0
        return int(self._payload.get("final_count") or 0)

    @property
    def active(self) -> bool:
        return self._started_monotonic is not None

    @property
    def armed(self) -> bool:
        return self._payload is not None

    @property
    def is_finished(self) -> bool:
        return bool(self._receipts) and self._cursor >= len(self._receipts)

    def prepare(self, *, video_path: Path, calibration_path: Path, model_path: Path) -> None:
        resolved_video = video_path.expanduser().resolve()
        resolved_calibration = calibration_path.expanduser().resolve()
        resolved_model = model_path.expanduser().resolve()

        payload, report_path = self._load_matching_payload(
            video_path=resolved_video,
            calibration_path=resolved_calibration,
            model_path=resolved_model,
        )
        if payload is None or report_path is None:
            payload, report_path = self._build_payload(
                video_path=resolved_video,
                calibration_path=resolved_calibration,
                model_path=resolved_model,
            )

        self._payload = payload
        self._report_path = report_path
        self._receipts = [
            DemoReceipt(
                event_ts=float(item.get("event_ts") or 0.0),
                track_id=int(item.get("track_id") or 0),
                count_authority=item.get("count_authority"),
                payload=dict(item),
            )
            for item in sorted(payload.get("events") or [], key=lambda entry: float(entry.get("event_ts") or 0.0))
        ]
        self.disarm()

    def arm(self, *, playback_speed: float) -> None:
        if self._payload is None:
            raise RuntimeError("Deterministic demo runner is not prepared")
        self._playback_speed = max(0.25, float(playback_speed))
        self._cursor = 0
        self._started_monotonic = None

    def disarm(self) -> None:
        self._cursor = 0
        self._started_monotonic = None

    def activate(self, *, start_monotonic: float | None = None) -> None:
        if self._payload is None:
            raise RuntimeError("Deterministic demo runner is not prepared")
        if self._started_monotonic is None:
            self._started_monotonic = float(start_monotonic if start_monotonic is not None else time.monotonic())

    def drain_due_events(self, *, now_monotonic: float | None = None) -> list[dict[str, Any]]:
        if self._payload is None or self._started_monotonic is None:
            return []

        now = float(now_monotonic if now_monotonic is not None else time.monotonic())
        revealed_video_seconds = max(0.0, now - self._started_monotonic) * self._playback_speed
        due: list[dict[str, Any]] = []
        while self._cursor < len(self._receipts) and self._receipts[self._cursor].event_ts <= revealed_video_seconds + 1e-9:
            due.append(dict(self._receipts[self._cursor].payload))
            self._cursor += 1
        return due

    def _load_matching_payload(
        self,
        *,
        video_path: Path,
        calibration_path: Path,
        model_path: Path,
    ) -> tuple[dict[str, Any] | None, Path | None]:
        candidates: list[Path] = []
        if self._cache_path is not None:
            candidates.append(self._cache_path.expanduser().resolve())
        else:
            candidates.extend(sorted(self._report_dir.glob("*runtime_event_audit*.json"), key=lambda path: path.stat().st_mtime, reverse=True))

        for path in candidates:
            payload = self._read_payload(path)
            if payload is None:
                continue
            if not self._payload_matches(
                payload,
                video_path=video_path,
                calibration_path=calibration_path,
                model_path=model_path,
            ):
                continue
            return payload, path.resolve()
        return None, None

    def _build_payload(
        self,
        *,
        video_path: Path,
        calibration_path: Path,
        model_path: Path,
    ) -> tuple[dict[str, Any], Path]:
        from scripts.audit_factory2_runtime_events import audit_runtime_events

        stem = video_path.stem or "demo"
        output_path = self._report_dir / f"{stem}_runtime_event_audit.deterministic_demo.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = audit_runtime_events(
            video_path=video_path,
            calibration_path=calibration_path,
            model_path=model_path,
            output_path=output_path,
            start_seconds=0.0,
            end_seconds=None,
            processing_fps=10.0,
            include_track_histories=False,
            force=True,
        )
        return payload, output_path.resolve()

    def _payload_matches(
        self,
        payload: dict[str, Any],
        *,
        video_path: Path,
        calibration_path: Path,
        model_path: Path,
    ) -> bool:
        if payload.get("schema_version") != AUDIT_SCHEMA_VERSION:
            return False
        if float(payload.get("start_seconds") or 0.0) != 0.0:
            return False
        if payload.get("end_seconds") not in {None, 0, 0.0}:
            return False
        if self._resolve_payload_path(payload.get("video_path")) != video_path:
            return False
        if self._resolve_payload_path(payload.get("calibration_path")) != calibration_path:
            return False
        if self._resolve_payload_path(payload.get("model_path")) != model_path:
            return False
        return isinstance(payload.get("events"), list)

    def _read_payload(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _resolve_payload_path(self, value: Any) -> Path | None:
        if not value:
            return None
        try:
            return Path(str(value)).expanduser().resolve()
        except OSError:
            return None
