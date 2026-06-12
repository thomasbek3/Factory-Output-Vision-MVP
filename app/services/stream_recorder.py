from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "factory-vision-stream-segment-manifest-v1"
DEFAULT_PRIVACY_MODE = "offline_local"
SEGMENT_EXTENSIONS = {".mkv", ".mp4", ".ts", ".mov"}
SEGMENT_MANIFEST_REQUIRED_KEYS = {
    "schema_version",
    "station_id",
    "source_uri_hash",
    "privacy_mode",
    "segment_seconds",
    "retention_minutes",
    "segments",
    "updated_at",
}
SEGMENT_ROW_REQUIRED_KEYS = {
    "station_id",
    "segment_id",
    "path",
    "file_size_bytes",
    "sha256",
    "source_uri_hash",
    "start_wall_ts",
    "end_wall_ts",
    "duration_sec",
    "codec",
    "container",
    "width",
    "height",
    "fps_estimate",
    "decode_ok",
    "frame_gaps",
    "privacy_mode",
    "pinned_reason",
    "probe_error",
}

ProbeRunner = Callable[[Path], dict[str, Any]]


@dataclass(frozen=True)
class SegmentMetadata:
    station_id: str
    segment_id: str
    path: str
    file_size_bytes: int
    sha256: str
    source_uri_hash: str
    start_wall_ts: str | None
    end_wall_ts: str | None
    duration_sec: float | None
    codec: str | None
    container: str
    width: int | None
    height: int | None
    fps_estimate: float | None
    decode_ok: bool
    frame_gaps: list[dict[str, Any]]
    privacy_mode: str
    pinned_reason: str | None
    probe_error: str | None = None


def safe_station_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return slug or "station"


def source_uri_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_manifest_time(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_recording_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def redacted_source_label(source: str) -> str:
    parts = urlsplit(source)
    if not parts.scheme or not parts.netloc:
        return "<source-redacted>"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"<credentials>@{host}" if "@" in parts.netloc else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def redact_source_text(text: str, source: str) -> str:
    redacted = text.replace(source, redacted_source_label(source))
    parts = urlsplit(source)
    if "@" in parts.netloc:
        raw_credentials = parts.netloc.rsplit("@", 1)[0]
        redacted = redacted.replace(f"{raw_credentials}@", "<credentials>@")
    return redacted


class StreamSegmentRecorder:
    """Sidecar recorder for durable RTSP/file segment evidence.

    This service intentionally does not feed `VisionWorker`; it records replayable
    chunks for onboarding and audit while the existing runtime keeps count
    authority.
    """

    def __init__(
        self,
        *,
        source: str,
        station_id: str,
        output_root: Path,
        segment_seconds: int = 60,
        retention_minutes: int = 30,
        container: str = "mkv",
        privacy_mode: str = DEFAULT_PRIVACY_MODE,
        realtime_file_input: bool = False,
        recording_id: str | None = None,
        maintenance_interval_sec: float = 10.0,
    ) -> None:
        if segment_seconds <= 0:
            raise ValueError("segment_seconds must be positive")
        if retention_minutes <= 0:
            raise ValueError("retention_minutes must be positive")
        if maintenance_interval_sec <= 0:
            raise ValueError("maintenance_interval_sec must be positive")
        normalized_container = container.lower().lstrip(".")
        if f".{normalized_container}" not in SEGMENT_EXTENSIONS:
            raise ValueError(f"container must be one of: {', '.join(sorted(SEGMENT_EXTENSIONS))}")
        self.source = source
        self.station_id = safe_station_id(station_id)
        self.output_root = output_root.expanduser().resolve()
        self.segment_seconds = int(segment_seconds)
        self.retention_minutes = int(retention_minutes)
        self.container = normalized_container
        self.privacy_mode = privacy_mode
        self.realtime_file_input = bool(realtime_file_input)
        self.recording_id = safe_station_id(recording_id) if recording_id else build_recording_id()
        self.maintenance_interval_sec = float(maintenance_interval_sec)

    @property
    def station_dir(self) -> Path:
        return self.output_root / self.station_id

    @property
    def segment_dir(self) -> Path:
        return self.station_dir / "segments"

    @property
    def manifest_path(self) -> Path:
        return self.station_dir / "segment_manifest.json"

    def build_ffmpeg_command(self) -> list[str]:
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        if self._is_rtsp_source():
            cmd += ["-rtsp_transport", "tcp"]
        elif self.realtime_file_input:
            cmd += ["-re"]
        filename_pattern = self._segment_filename_pattern()
        cmd += ["-i", self.source, "-map", "0:v:0", "-an", "-c", "copy"]
        cmd += [
            "-f",
            "segment",
            "-segment_time",
            str(self.segment_seconds),
            "-reset_timestamps",
            "1",
        ]
        if self._uses_wall_clock_filenames():
            cmd += ["-strftime", "1"]
        cmd.append(str(self.segment_dir / filename_pattern))
        return cmd

    def run(self, *, duration_sec: float | None = None) -> dict[str, Any]:
        """Run ffmpeg until EOF, interrupt, or optional duration limit."""
        started_at = utc_now_iso()
        existing_paths = {str(path) for path in self.list_segment_files()}
        stderr_tail = _BoundedTextTail()
        process = subprocess.Popen(
            self.build_ffmpeg_command(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        stderr_thread: threading.Thread | None = None
        if process.stderr:
            stderr_thread = threading.Thread(target=_drain_stderr, args=(process.stderr, stderr_tail), daemon=True)
            stderr_thread.start()
        timed_out = False
        interrupted = False
        deadline = None if duration_sec is None else time.monotonic() + max(float(duration_sec), 0.1)
        next_maintenance = time.monotonic() + self.maintenance_interval_sec
        try:
            while process.poll() is None:
                now = time.monotonic()
                if deadline is not None and now >= deadline:
                    timed_out = True
                    self._terminate_process(process)
                    break
                if now >= next_maintenance:
                    self._run_maintenance()
                    next_maintenance = now + self.maintenance_interval_sec
                time.sleep(0.25)
        except KeyboardInterrupt:
            interrupted = True
            self._terminate_process(process)
        except Exception:
            if process.poll() is None:
                self._terminate_process(process)
            raise
        finally:
            if stderr_thread:
                stderr_thread.join(timeout=2)
        manifest = self.refresh_manifest()
        retention = self.enforce_retention()
        manifest = self.read_manifest()
        new_segments = [row for row in manifest["segments"] if row.get("path") not in existing_paths]
        new_valid_segments = [row for row in new_segments if row.get("decode_ok")]
        return {
            "station_id": self.station_id,
            "started_at": started_at,
            "ended_at": utc_now_iso(),
            "returncode": process.returncode,
            "timed_out": timed_out,
            "interrupted": interrupted,
            "stderr": redact_source_text(stderr_tail.text().strip(), self.source),
            "manifest_path": str(self.manifest_path),
            "segment_count": len(manifest["segments"]),
            "new_segment_count": len(new_segments),
            "new_valid_segment_count": len(new_valid_segments),
            "retention": retention,
        }

    def _run_maintenance(self) -> None:
        self.refresh_manifest()
        self.enforce_retention()

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def refresh_manifest(self, *, probe_runner: ProbeRunner | None = None) -> dict[str, Any]:
        manifest = self.read_manifest()
        segment_files = self.list_segment_files()
        segment_paths = {self._path_key(path) for path in segment_files}
        by_path: dict[str, dict[str, Any]] = {}
        for row in manifest["segments"]:
            for row_path_key in self._manifest_row_path_keys(row):
                if row_path_key in segment_paths and row_path_key not in by_path:
                    by_path[row_path_key] = row
        probe = probe_runner or ffprobe_segment
        for segment_path in segment_files:
            path_key = self._path_key(segment_path)
            existing = by_path.get(path_key)
            pinned_reason = existing.get("pinned_reason") if existing else None
            stat = segment_path.stat()
            end_wall_ts = iso_from_timestamp(stat.st_mtime)
            unchanged = (
                existing
                and existing.get("file_size_bytes") == stat.st_size
                and existing.get("end_wall_ts") == end_wall_ts
                and existing.get("sha256")
                and "decode_ok" in existing
            )
            if unchanged:
                row = dict(existing)
                row["path"] = str(segment_path)
                row["pinned_reason"] = pinned_reason
                row["privacy_mode"] = self.privacy_mode
            else:
                row = asdict(
                    build_segment_metadata(
                        path=segment_path,
                        source=self.source,
                        station_id=self.station_id,
                        privacy_mode=self.privacy_mode,
                        pinned_reason=pinned_reason,
                        probe_runner=probe,
                    )
                )
            if unchanged and existing and existing.get("source_uri_hash"):
                row["source_uri_hash"] = existing["source_uri_hash"]
            by_path[path_key] = row
        manifest["station_id"] = self.station_id
        manifest["source_uri_hash"] = source_uri_hash(self.source)
        manifest["privacy_mode"] = self.privacy_mode
        manifest["segment_seconds"] = self.segment_seconds
        manifest["retention_minutes"] = self.retention_minutes
        manifest["segments"] = sorted(by_path.values(), key=lambda row: (row.get("start_wall_ts") or "", row["path"]))
        manifest["updated_at"] = utc_now_iso()
        validate_segment_manifest(manifest)
        self.write_manifest(manifest)
        return manifest

    def read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "station_id": self.station_id,
                "source_uri_hash": source_uri_hash(self.source),
                "privacy_mode": self.privacy_mode,
                "segment_seconds": self.segment_seconds,
                "retention_minutes": self.retention_minutes,
                "segments": [],
                "updated_at": utc_now_iso(),
            }
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported segment manifest schema: {payload.get('schema_version')}")
        return payload

    def write_manifest(self, payload: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def pin_segment(self, *, segment_id: str, reason: str) -> dict[str, Any]:
        manifest = self.read_manifest()
        found = False
        for row in manifest["segments"]:
            if row.get("segment_id") == segment_id:
                row["pinned_reason"] = reason
                found = True
        if not found:
            raise ValueError(f"unknown segment_id: {segment_id}")
        manifest["updated_at"] = utc_now_iso()
        self.write_manifest(manifest)
        return manifest

    def enforce_retention(self, *, now_ts: float | None = None) -> dict[str, Any]:
        now_value = time.time() if now_ts is None else float(now_ts)
        cutoff = now_value - (self.retention_minutes * 60)
        manifest = self.read_manifest()
        kept: list[dict[str, Any]] = []
        deleted: list[str] = []
        for row in manifest["segments"]:
            path = Path(str(row["path"]))
            pinned = bool(row.get("pinned_reason"))
            end_ts = parse_manifest_time(row.get("end_wall_ts"))
            if pinned or end_ts is None or end_ts >= cutoff:
                kept.append(row)
                continue
            if path.exists():
                path.unlink()
            deleted.append(str(path))
        if deleted:
            manifest["segments"] = kept
            manifest["updated_at"] = utc_now_iso()
            self.write_manifest(manifest)
        return {"deleted_count": len(deleted), "deleted_paths": deleted, "retention_minutes": self.retention_minutes}

    def list_segment_files(self) -> list[Path]:
        if not self.segment_dir.exists():
            return []
        return sorted(path for path in self.segment_dir.iterdir() if path.is_file() and path.suffix.lower() in SEGMENT_EXTENSIONS)

    def _path_key(self, path: Path) -> str:
        return str(path.expanduser().resolve())

    def _manifest_row_path_keys(self, row: dict[str, Any]) -> set[str]:
        raw_path = row.get("path")
        if not raw_path:
            return set()
        path = Path(str(raw_path)).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates.extend(
                [
                    self.output_root.parent / path,
                    self.output_root / path,
                    self.station_dir / path,
                    self.segment_dir / path.name,
                ]
            )
        return {self._path_key(candidate) for candidate in candidates}

    def _is_rtsp_source(self) -> bool:
        return self.source.lower().startswith("rtsp://")

    def _uses_wall_clock_filenames(self) -> bool:
        return self._is_rtsp_source() or self.realtime_file_input

    def _segment_filename_pattern(self) -> str:
        if self._uses_wall_clock_filenames():
            return f"%Y%m%dT%H%M%S_{self.recording_id}.{self.container}"
        return f"{self.recording_id}_%06d.{self.container}"


def build_segment_metadata(
    *,
    path: Path,
    source: str,
    station_id: str,
    privacy_mode: str,
    pinned_reason: str | None,
    probe_runner: ProbeRunner,
) -> SegmentMetadata:
    probe_error: str | None = None
    try:
        probe = probe_runner(path)
        decode_ok = True
    except Exception as exc:  # noqa: BLE001
        probe = {}
        probe_error = str(exc)
        decode_ok = False
    duration = _optional_float(probe.get("duration_sec"))
    stat = path.stat()
    end_ts = stat.st_mtime
    start_ts = end_ts - duration if duration is not None else None
    return SegmentMetadata(
        station_id=station_id,
        segment_id=path.stem,
        path=str(path),
        file_size_bytes=stat.st_size,
        sha256=sha256_file(path),
        source_uri_hash=source_uri_hash(source),
        start_wall_ts=iso_from_timestamp(start_ts) if start_ts is not None else None,
        end_wall_ts=iso_from_timestamp(end_ts),
        duration_sec=duration,
        codec=_optional_str(probe.get("codec")),
        container=path.suffix.lower().lstrip("."),
        width=_optional_int(probe.get("width")),
        height=_optional_int(probe.get("height")),
        fps_estimate=_optional_float(probe.get("fps")),
        decode_ok=decode_ok,
        frame_gaps=[],
        privacy_mode=privacy_mode,
        pinned_reason=pinned_reason,
        probe_error=probe_error,
    )


def ffprobe_segment(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-select_streams",
        "v:0",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError("No video stream detected")
    stream = streams[0]
    fmt = payload.get("format") or {}
    duration = _optional_float(stream.get("duration"))
    if duration is None:
        duration = _optional_float(fmt.get("duration"))
    validate_segment_decode(path, duration_sec=duration)
    rate_text = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
    fps = _parse_frame_rate(str(rate_text))
    return {
        "width": _optional_int(stream.get("width")),
        "height": _optional_int(stream.get("height")),
        "fps": fps,
        "codec": stream.get("codec_name"),
        "duration_sec": duration,
    }


def validate_segment_decode(path: Path, *, duration_sec: float | None = None) -> None:
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-xerror",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=decode_validation_timeout(duration_sec))
    if result.returncode != 0 or result.stderr.strip():
        error = result.stderr.strip() or f"ffmpeg decode failed with code {result.returncode}"
        raise RuntimeError(error)


def decode_validation_timeout(duration_sec: float | None) -> float:
    if duration_sec is None:
        return 60.0
    return max(30.0, min(300.0, (float(duration_sec) * 3.0) + 15.0))


def load_manifest_segments(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported segment manifest schema: {payload.get('schema_version')}")
    return list(payload.get("segments") or [])


def validate_segment_manifest(payload: dict[str, Any]) -> None:
    missing = sorted(SEGMENT_MANIFEST_REQUIRED_KEYS - set(payload))
    if missing:
        raise ValueError(f"segment manifest missing required key(s): {', '.join(missing)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported segment manifest schema: {payload.get('schema_version')}")
    if not isinstance(payload.get("segments"), list):
        raise ValueError("segment manifest segments must be a list")
    if "source_uri" in payload or "source" in payload:
        raise ValueError("segment manifest must not store raw source URIs")
    for index, row in enumerate(payload["segments"]):
        if not isinstance(row, dict):
            raise ValueError(f"segment row {index} must be an object")
        row_missing = sorted(SEGMENT_ROW_REQUIRED_KEYS - set(row))
        if row_missing:
            raise ValueError(f"segment row {index} missing required key(s): {', '.join(row_missing)}")
        if "source_uri" in row or "source" in row:
            raise ValueError(f"segment row {index} must not store raw source URIs")


def _parse_frame_rate(value: str) -> float | None:
    try:
        if "/" in value:
            num_text, denom_text = value.split("/", 1)
            denom = float(denom_text)
            return None if denom == 0 else round(float(num_text) / denom, 3)
        return round(float(value), 3)
    except ValueError:
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return round(parsed, 3)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def write_segments_summary(path: Path, segments: Iterable[dict[str, Any]]) -> None:
    rows = list(segments)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"segments": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class _BoundedTextTail:
    def __init__(self, *, limit_chars: int = 20_000) -> None:
        self.limit_chars = limit_chars
        self._text = ""
        self._lock = threading.Lock()

    def append(self, chunk: str) -> None:
        with self._lock:
            self._text = (self._text + chunk)[-self.limit_chars :]

    def text(self) -> str:
        with self._lock:
            return self._text


def _drain_stderr(stream: TextIO, tail: _BoundedTextTail) -> None:
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            tail.append(chunk)
    finally:
        stream.close()
