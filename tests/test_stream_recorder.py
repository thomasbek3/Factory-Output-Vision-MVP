from __future__ import annotations

from dataclasses import asdict
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.stream_recorder import (
    SCHEMA_VERSION,
    StreamSegmentRecorder,
    build_segment_metadata,
    ffprobe_segment,
    load_manifest_segments,
    redact_source_text,
    source_uri_hash,
    validate_segment_decode,
)
from scripts import record_stream_segments


def test_build_ffmpeg_command_segments_rtsp_without_exposing_source_in_manifest(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(
        source="rtsp://user:password@example.local/Preview_01_main",
        station_id="Line 1",
        output_root=tmp_path,
        recording_id="rtsp_run",
    )

    command = recorder.build_ffmpeg_command()

    assert command[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
    assert "-rtsp_transport" in command
    assert "tcp" in command
    assert "-f" in command
    assert "segment" in command
    assert "-segment_time" in command
    assert "60" in command
    assert command[-1].endswith("Line_1/segments/%Y%m%dT%H%M%S_rtsp_run.mkv")


def test_build_ffmpeg_command_uses_indexed_segments_for_unthrottled_file_input(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(
        source="/tmp/input.mp4",
        station_id="Line 1",
        output_root=tmp_path,
        segment_seconds=1,
        recording_id="run_1",
    )

    command = recorder.build_ffmpeg_command()

    assert "-strftime" not in command
    assert command[-1].endswith("Line_1/segments/run_1_%06d.mkv")


def test_file_input_default_recording_ids_do_not_reuse_segment_names(tmp_path: Path) -> None:
    first = StreamSegmentRecorder(source="/tmp/input.mp4", station_id="Line 1", output_root=tmp_path)
    second = StreamSegmentRecorder(source="/tmp/input.mp4", station_id="Line 1", output_root=tmp_path)

    assert first.build_ffmpeg_command()[-1] != second.build_ffmpeg_command()[-1]


def test_refresh_manifest_records_new_segments_with_hash_and_probe_metadata(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(
        source="rtsp://camera.local/live",
        station_id="station-a",
        output_root=tmp_path,
        segment_seconds=30,
        retention_minutes=45,
    )
    recorder.segment_dir.mkdir(parents=True)
    segment = recorder.segment_dir / "20260608T120000.mkv"
    segment.write_bytes(b"segment-bytes")

    def fake_probe(path: Path) -> dict:
        assert path == segment
        return {"duration_sec": 30.0, "codec": "h264", "width": 1920, "height": 1080, "fps": 15.0}

    manifest = recorder.refresh_manifest(probe_runner=fake_probe)

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["source_uri_hash"] == source_uri_hash("rtsp://camera.local/live")
    assert len(manifest["segments"]) == 1
    row = manifest["segments"][0]
    assert row["segment_id"] == "20260608T120000"
    assert row["duration_sec"] == 30.0
    assert row["codec"] == "h264"
    assert row["decode_ok"] is True
    assert row["privacy_mode"] == "offline_local"
    assert "rtsp://camera.local/live" not in json.dumps(manifest)
    assert load_manifest_segments(recorder.manifest_path)[0]["sha256"]


def test_ffprobe_segment_requires_decodable_video_frames(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for decode validation")
    source = tmp_path / "source.mkv"
    truncated = tmp_path / "truncated.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x120:rate=5",
            "-t",
            "4",
            "-c:v",
            "libx264",
            source,
        ],
        check=True,
    )
    source_bytes = source.read_bytes()
    truncated.write_bytes(source_bytes[: min(4000, len(source_bytes) - 1)])

    metadata = build_segment_metadata(
        path=truncated,
        source="file.mp4",
        station_id="station-a",
        privacy_mode="offline_local",
        pinned_reason=None,
        probe_runner=ffprobe_segment,
    )

    assert metadata.decode_ok is False
    assert metadata.probe_error


def test_validate_segment_decode_timeout_scales_with_duration(monkeypatch, tmp_path: Path) -> None:
    observed: dict[str, float] = {}

    def fake_run(cmd, *, capture_output: bool, text: bool, timeout: float):
        observed["timeout"] = timeout
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("app.services.stream_recorder.subprocess.run", fake_run)

    validate_segment_decode(tmp_path / "segment.mkv", duration_sec=60.0)

    assert observed["timeout"] >= 180.0


def test_refresh_manifest_preserves_existing_segment_source_hash(tmp_path: Path) -> None:
    first = StreamSegmentRecorder(source="file-a.mp4", station_id="station-a", output_root=tmp_path)
    first.segment_dir.mkdir(parents=True)
    segment = first.segment_dir / "segment.mkv"
    segment.write_bytes(b"segment-bytes")

    first.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})
    initial_row = first.read_manifest()["segments"][0]

    second = StreamSegmentRecorder(source="file-b.mp4", station_id="station-a", output_root=tmp_path)
    second.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})
    refreshed = second.read_manifest()

    assert refreshed["source_uri_hash"] == source_uri_hash("file-b.mp4")
    assert refreshed["segments"][0]["source_uri_hash"] == initial_row["source_uri_hash"]


def test_refresh_manifest_updates_source_hash_when_existing_path_changes(tmp_path: Path) -> None:
    first = StreamSegmentRecorder(source="file-a.mp4", station_id="station-a", output_root=tmp_path)
    first.segment_dir.mkdir(parents=True)
    segment = first.segment_dir / "segment.mkv"
    segment.write_bytes(b"segment-a")

    first.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})

    segment.write_bytes(b"segment-b-longer")
    second = StreamSegmentRecorder(source="file-b.mp4", station_id="station-a", output_root=tmp_path)
    refreshed = second.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})

    assert refreshed["segments"][0]["source_uri_hash"] == source_uri_hash("file-b.mp4")


def test_refresh_manifest_reuses_unchanged_segment_metadata(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(source="file-a.mp4", station_id="station-a", output_root=tmp_path)
    recorder.segment_dir.mkdir(parents=True)
    segment = recorder.segment_dir / "segment.mkv"
    segment.write_bytes(b"segment-bytes")
    calls = 0

    def fake_probe(path: Path) -> dict:
        nonlocal calls
        calls += 1
        return {"duration_sec": 1.0, "codec": "h264", "width": 160, "height": 120, "fps": 5.0}

    recorder.refresh_manifest(probe_runner=fake_probe)
    recorder.refresh_manifest(probe_runner=fake_probe)

    assert calls == 1


def test_refresh_manifest_preserves_pin_from_legacy_relative_path_manifest(tmp_path: Path) -> None:
    previous_cwd = Path.cwd()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    try:
        os.chdir(work_dir)
        recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=Path("recordings"), retention_minutes=1)
        recorder.segment_dir.mkdir(parents=True)
        segment = recorder.segment_dir / "segment.mkv"
        segment.write_bytes(b"segment")
        old_ts = time.time() - 3600
        os.utime(segment, (old_ts, old_ts))
        probe = lambda path: {"duration_sec": 1.0, "codec": "h264", "width": 160, "height": 120, "fps": 5.0}
        old_row = asdict(
            build_segment_metadata(
                path=segment,
                source="/tmp/source.mp4",
                station_id="line-a",
                privacy_mode="offline_local",
                pinned_reason="onboarding_holdout",
                probe_runner=probe,
            )
        )
        old_row["path"] = str(Path("recordings") / "line-a" / "segments" / "segment.mkv")
        recorder.write_manifest(
            {
                "schema_version": SCHEMA_VERSION,
                "station_id": "line-a",
                "source_uri_hash": source_uri_hash("/tmp/source.mp4"),
                "privacy_mode": "offline_local",
                "segment_seconds": 60,
                "retention_minutes": 1,
                "segments": [old_row],
                "updated_at": "2026-06-08T12:00:00Z",
            }
        )

        refreshed = recorder.refresh_manifest(probe_runner=probe)

        row = refreshed["segments"][0]
        assert row["path"] == str(segment)
        assert row["pinned_reason"] == "onboarding_holdout"
        retention = recorder.enforce_retention(now_ts=time.time())
        assert retention["deleted_count"] == 0
        assert segment.exists()
    finally:
        os.chdir(previous_cwd)


def test_refresh_manifest_updates_top_level_run_settings(tmp_path: Path) -> None:
    first = StreamSegmentRecorder(
        source="file-a.mp4",
        station_id="station-a",
        output_root=tmp_path,
        segment_seconds=60,
        retention_minutes=30,
        privacy_mode="offline_local",
    )
    first.write_manifest(first.read_manifest())

    second = StreamSegmentRecorder(
        source="file-b.mp4",
        station_id="station-a",
        output_root=tmp_path,
        segment_seconds=10,
        retention_minutes=5,
        privacy_mode="offline_lab",
    )
    manifest = second.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})

    assert manifest["source_uri_hash"] == source_uri_hash("file-b.mp4")
    assert manifest["segment_seconds"] == 10
    assert manifest["retention_minutes"] == 5
    assert manifest["privacy_mode"] == "offline_lab"


def test_refresh_manifest_drops_rows_for_missing_segment_files(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(source="file-a.mp4", station_id="station-a", output_root=tmp_path)
    recorder.write_manifest(
        {
            "schema_version": SCHEMA_VERSION,
            "station_id": "station-a",
            "source_uri_hash": source_uri_hash("file-a.mp4"),
            "privacy_mode": "offline_local",
            "segment_seconds": 60,
            "retention_minutes": 30,
            "updated_at": "2026-06-08T12:00:00Z",
            "segments": [
                {
                    "segment_id": "missing",
                    "path": str(recorder.segment_dir / "missing.mkv"),
                    "decode_ok": True,
                    "end_wall_ts": "2999-01-01T00:00:00Z",
                    "pinned_reason": None,
                }
            ],
        }
    )

    manifest = recorder.refresh_manifest(probe_runner=lambda path: {"duration_sec": 1.0})

    assert manifest["segments"] == []


def test_redact_source_text_removes_rtsp_credentials() -> None:
    source = "rtsp://user:secret@example.local:554/Preview_01_main"
    stderr = f"Error opening input file {source}.\nConnection to tcp://user:secret@example.local:554 failed."

    redacted = redact_source_text(stderr, source)

    assert source not in redacted
    assert "secret" not in redacted
    assert "user:secret" not in redacted
    assert "rtsp://<credentials>@example.local:554/Preview_01_main" in redacted


def test_redact_source_text_drops_query_tokens() -> None:
    source = "rtsp://camera.local/stream?user=admin&password=secret"
    stderr = f"Error opening input file {source}."

    redacted = redact_source_text(stderr, source)

    assert "password" not in redacted
    assert "secret" not in redacted
    assert "user=admin" not in redacted
    assert "rtsp://camera.local/stream" in redacted
    assert "?" not in redacted


def test_retention_deletes_old_unpinned_segments_and_keeps_pinned_segments(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(
        source="/tmp/video.mp4",
        station_id="station-a",
        output_root=tmp_path,
        retention_minutes=30,
    )
    recorder.segment_dir.mkdir(parents=True)
    old_segment = recorder.segment_dir / "old.mkv"
    pinned_segment = recorder.segment_dir / "pinned.mkv"
    fresh_segment = recorder.segment_dir / "fresh.mkv"
    for path in (old_segment, pinned_segment, fresh_segment):
        path.write_bytes(path.name.encode("utf-8"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "station_id": "station-a",
        "source_uri_hash": source_uri_hash("/tmp/video.mp4"),
        "privacy_mode": "offline_local",
        "segment_seconds": 60,
        "retention_minutes": 30,
        "updated_at": "2026-06-08T12:00:00Z",
        "segments": [
            {
                "segment_id": "old",
                "path": str(old_segment),
                "end_wall_ts": "2026-06-08T11:00:00Z",
                "pinned_reason": None,
            },
            {
                "segment_id": "pinned",
                "path": str(pinned_segment),
                "end_wall_ts": "2026-06-08T11:00:00Z",
                "pinned_reason": "onboarding_holdout",
            },
            {
                "segment_id": "fresh",
                "path": str(fresh_segment),
                "end_wall_ts": "2026-06-08T11:45:00Z",
                "pinned_reason": None,
            },
        ],
    }
    recorder.write_manifest(manifest)

    result = recorder.enforce_retention(now_ts=1717848000.0)

    # The explicit timestamp above is before the manifest rows, so nothing is old yet.
    assert result["deleted_count"] == 0
    result = recorder.enforce_retention(now_ts=1780920000.0)  # 2026-06-08T12:00:00Z

    assert result["deleted_count"] == 1
    assert old_segment.exists() is False
    assert pinned_segment.exists() is True
    assert fresh_segment.exists() is True
    rows = load_manifest_segments(recorder.manifest_path)
    assert [row["segment_id"] for row in rows] == ["pinned", "fresh"]


def test_record_stream_cli_returns_failure_for_ffmpeg_error(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeRecorder:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, *, duration_sec: float | None = None) -> dict:
            return {
                "returncode": 254,
                "timed_out": False,
                "segment_count": 0,
                "new_valid_segment_count": 0,
                "stderr": "source failed",
            }

    monkeypatch.setattr(record_stream_segments, "StreamSegmentRecorder", FakeRecorder)

    exit_code = record_stream_segments.main(
        ["--source", "/tmp/missing.mp4", "--station-id", "bad", "--output-root", str(tmp_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"returncode": 254' in captured.out
    assert "error: ffmpeg exited with code 254" in captured.err


def test_record_stream_cli_catches_constructor_validation_errors(tmp_path: Path, capsys) -> None:
    exit_code = record_stream_segments.main(
        ["--source", "/tmp/input.mp4", "--station-id", "bad", "--output-root", str(tmp_path), "--segment-seconds", "0"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "error: segment_seconds must be positive" in captured.err


def test_record_stream_cli_rejects_timeout_without_new_valid_segment(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeRecorder:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, *, duration_sec: float | None = None) -> dict:
            return {
                "returncode": -15,
                "timed_out": True,
                "segment_count": 1,
                "new_valid_segment_count": 0,
                "stderr": "terminated",
            }

    monkeypatch.setattr(record_stream_segments, "StreamSegmentRecorder", FakeRecorder)

    exit_code = record_stream_segments.main(
        ["--source", "/tmp/missing.mp4", "--station-id", "bad", "--output-root", str(tmp_path), "--duration-sec", "1"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"new_valid_segment_count": 0' in captured.out
    assert "error: ffmpeg exited with code -15" in captured.err


def test_record_stream_cli_rejects_success_without_new_valid_segment(monkeypatch, tmp_path: Path, capsys) -> None:
    class FakeRecorder:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, *, duration_sec: float | None = None) -> dict:
            return {
                "returncode": 0,
                "timed_out": False,
                "segment_count": 1,
                "new_valid_segment_count": 0,
                "stderr": "",
            }

    monkeypatch.setattr(record_stream_segments, "StreamSegmentRecorder", FakeRecorder)

    exit_code = record_stream_segments.main(
        ["--source", "/tmp/input.mp4", "--station-id", "bad", "--output-root", str(tmp_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error: no new valid segments recorded" in captured.err


def test_record_stream_cli_allows_bounded_stop_with_new_valid_segment(monkeypatch, tmp_path: Path) -> None:
    class FakeRecorder:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, *, duration_sec: float | None = None) -> dict:
            return {
                "returncode": -15,
                "timed_out": True,
                "interrupted": False,
                "segment_count": 1,
                "new_valid_segment_count": 1,
                "stderr": "terminated",
            }

    monkeypatch.setattr(record_stream_segments, "StreamSegmentRecorder", FakeRecorder)

    exit_code = record_stream_segments.main(
        ["--source", "/tmp/input.mp4", "--station-id", "ok", "--output-root", str(tmp_path), "--duration-sec", "1"]
    )

    assert exit_code == 0


def test_record_stream_cli_allows_manual_interrupt_with_new_valid_segment(monkeypatch, tmp_path: Path) -> None:
    class FakeRecorder:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def run(self, *, duration_sec: float | None = None) -> dict:
            return {
                "returncode": 255,
                "timed_out": False,
                "interrupted": True,
                "segment_count": 1,
                "new_valid_segment_count": 1,
                "stderr": "",
            }

    monkeypatch.setattr(record_stream_segments, "StreamSegmentRecorder", FakeRecorder)

    exit_code = record_stream_segments.main(
        ["--source", "/tmp/input.mp4", "--station-id", "ok", "--output-root", str(tmp_path)]
    )

    assert exit_code == 0
