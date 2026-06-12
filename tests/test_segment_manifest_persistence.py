from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from app.db.database import init_db
from app.db.segment_repo import list_recorded_segments, pin_recorded_segment, upsert_segment_manifest
from app.services.stream_recorder import (
    SCHEMA_VERSION,
    StreamSegmentRecorder,
    source_uri_hash,
    validate_segment_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_stream_segment_manifest_schema_is_present_and_matches_recorder_contract() -> None:
    schema = json.loads((REPO_ROOT / "validation/schemas/stream_segment_manifest.schema.json").read_text())

    assert schema["type"] == "object"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert set(schema["required"]) == {
        "schema_version",
        "station_id",
        "source_uri_hash",
        "privacy_mode",
        "segment_seconds",
        "retention_minutes",
        "segments",
        "updated_at",
    }
    assert "source_uri" not in schema["properties"]


def test_refresh_manifest_validates_full_segment_rows_and_excludes_raw_source_uri(tmp_path: Path) -> None:
    recorder = StreamSegmentRecorder(
        source="rtsp://user:secret@example.local/Preview_01_main?token=hidden",
        station_id="line-a",
        output_root=tmp_path,
    )
    recorder.segment_dir.mkdir(parents=True)
    segment = recorder.segment_dir / "20260609T120000_run.mkv"
    segment.write_bytes(b"segment")

    manifest = recorder.refresh_manifest(
        probe_runner=lambda path: {"duration_sec": 60.0, "codec": "h264", "width": 1920, "height": 1080, "fps": 15.0}
    )

    validate_segment_manifest(manifest)
    serialized = json.dumps(manifest)
    assert "secret" not in serialized
    assert "token=hidden" not in serialized
    assert manifest["segments"][0]["source_uri_hash"] == source_uri_hash(
        "rtsp://user:secret@example.local/Preview_01_main?token=hidden"
    )


def test_segment_repo_upserts_manifest_rows_and_preserves_db_pin(tmp_path: Path) -> None:
    previous = os.environ.get("FC_DB_PATH")
    os.environ["FC_DB_PATH"] = str(tmp_path / "segments.db")
    try:
        init_db()
        recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=tmp_path)
        recorder.segment_dir.mkdir(parents=True)
        segment = recorder.segment_dir / "segment.mkv"
        segment.write_bytes(b"segment")
        manifest = recorder.refresh_manifest(
            probe_runner=lambda path: {"duration_sec": 1.0, "codec": "h264", "width": 160, "height": 120, "fps": 5.0}
        )

        assert upsert_segment_manifest(manifest=manifest) == 1
        pin_recorded_segment(station_id="line-a", segment_id="segment", reason="onboarding_holdout")
        rows = list_recorded_segments(station_id="line-a")
        assert rows[0]["pinned_reason"] == "onboarding_holdout"

        manifest["segments"][0]["pinned_reason"] = None
        assert upsert_segment_manifest(manifest=manifest) == 1

        rows = list_recorded_segments(station_id="line-a")
        assert rows[0]["decode_ok"] is True
        assert rows[0]["frame_gaps"] == []
        assert rows[0]["pinned_reason"] == "onboarding_holdout"
    finally:
        if previous is None:
            os.environ.pop("FC_DB_PATH", None)
        else:
            os.environ["FC_DB_PATH"] = previous


def test_db_pin_updates_manifest_so_retention_keeps_segment(tmp_path: Path) -> None:
    previous = os.environ.get("FC_DB_PATH")
    os.environ["FC_DB_PATH"] = str(tmp_path / "segments.db")
    try:
        init_db()
        recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=tmp_path, retention_minutes=1)
        recorder.segment_dir.mkdir(parents=True)
        segment = recorder.segment_dir / "segment.mkv"
        segment.write_bytes(b"segment")
        old_ts = time.time() - 3600
        os.utime(segment, (old_ts, old_ts))

        manifest = recorder.refresh_manifest(
            probe_runner=lambda path: {"duration_sec": 1.0, "codec": "h264", "width": 160, "height": 120, "fps": 5.0}
        )
        assert upsert_segment_manifest(manifest=manifest) == 1

        pin_recorded_segment(station_id="line-a", segment_id="segment", reason="onboarding_holdout")

        pinned_manifest = recorder.read_manifest()
        assert pinned_manifest["segments"][0]["pinned_reason"] == "onboarding_holdout"
        retention = recorder.enforce_retention(now_ts=time.time())
        assert retention["deleted_count"] == 0
        assert segment.exists()
    finally:
        if previous is None:
            os.environ.pop("FC_DB_PATH", None)
        else:
            os.environ["FC_DB_PATH"] = previous


def test_relative_recorder_output_root_stores_absolute_paths_for_db_pin(tmp_path: Path) -> None:
    previous_db = os.environ.get("FC_DB_PATH")
    previous_cwd = Path.cwd()
    os.environ["FC_DB_PATH"] = str(tmp_path / "segments.db")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    try:
        init_db()
        os.chdir(work_dir)
        recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=Path("recordings"), retention_minutes=1)
        recorder.segment_dir.mkdir(parents=True)
        segment = recorder.segment_dir / "segment.mkv"
        segment.write_bytes(b"segment")
        old_ts = time.time() - 3600
        os.utime(segment, (old_ts, old_ts))
        manifest = recorder.refresh_manifest(
            probe_runner=lambda path: {"duration_sec": 1.0, "codec": "h264", "width": 160, "height": 120, "fps": 5.0}
        )
        assert Path(manifest["segments"][0]["path"]).is_absolute()
        assert upsert_segment_manifest(manifest=manifest) == 1

        os.chdir(tmp_path)
        pin_recorded_segment(station_id="line-a", segment_id="segment", reason="onboarding_holdout")

        pinned_manifest = recorder.read_manifest()
        assert pinned_manifest["segments"][0]["pinned_reason"] == "onboarding_holdout"
        retention = recorder.enforce_retention(now_ts=time.time())
        assert retention["deleted_count"] == 0
        assert segment.exists()
    finally:
        os.chdir(previous_cwd)
        if previous_db is None:
            os.environ.pop("FC_DB_PATH", None)
        else:
            os.environ["FC_DB_PATH"] = previous_db


def test_validate_segment_manifest_rejects_raw_source_uri() -> None:
    with pytest.raises(ValueError, match="raw source"):
        validate_segment_manifest(
            {
                "schema_version": SCHEMA_VERSION,
                "station_id": "line-a",
                "source_uri": "rtsp://user:secret@example.local/live",
                "source_uri_hash": "a" * 64,
                "privacy_mode": "offline_local",
                "segment_seconds": 60,
                "retention_minutes": 30,
                "segments": [],
                "updated_at": "2026-06-09T12:00:00Z",
            }
        )
