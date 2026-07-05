from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.onboarding_windows import SCHEMA_VERSION, extract_candidate_windows
from app.services.stream_recorder import StreamSegmentRecorder, ffprobe_segment
from scripts.research.factory2 import extract_onboarding_windows


def _write_test_segment(path: Path) -> None:
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
            "3",
            "-c:v",
            "libx264",
            str(path),
        ],
        check=True,
    )


def test_extract_candidate_windows_from_segment_manifest_produces_playable_artifacts(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for onboarding window extraction")
    recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=tmp_path)
    recorder.segment_dir.mkdir(parents=True)
    segment = recorder.segment_dir / "segment.mkv"
    _write_test_segment(segment)
    manifest = recorder.refresh_manifest(probe_runner=ffprobe_segment)
    manifest_path = recorder.manifest_path

    payload = extract_candidate_windows(
        segment_manifest_path=manifest_path,
        output_dir=tmp_path / "windows",
        window_sec=0.5,
        force=True,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["segment_manifest_path"] == str(manifest_path)
    assert {row["candidate_type"] for row in payload["windows"]} == {
        "positive_candidate",
        "idle_candidate",
        "hard_negative_candidate",
    }
    assert len(payload["windows"]) == 3
    assert manifest["segments"][0]["segment_id"] == "segment"
    for row in payload["windows"]:
        assert row["label_status"] == "unreviewed"
        assert row["evidence_role"] == "candidate_only_not_truth"
        clip_path = Path(row["clip_path"])
        assert clip_path.exists()
        assert clip_path.stat().st_size > 0
        assert ffprobe_segment(clip_path)["duration_sec"] is not None


def test_extract_candidate_windows_refuses_overwrite_without_force(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for onboarding window extraction")
    recorder = StreamSegmentRecorder(source="/tmp/source.mp4", station_id="line-a", output_root=tmp_path)
    recorder.segment_dir.mkdir(parents=True)
    segment = recorder.segment_dir / "segment.mkv"
    _write_test_segment(segment)
    recorder.refresh_manifest(probe_runner=ffprobe_segment)

    extract_candidate_windows(
        segment_manifest_path=recorder.manifest_path,
        output_dir=tmp_path / "windows",
        window_sec=0.5,
        force=True,
    )

    with pytest.raises(FileExistsError):
        extract_candidate_windows(
            segment_manifest_path=recorder.manifest_path,
            output_dir=tmp_path / "windows",
            window_sec=0.5,
            force=False,
        )


def test_extract_onboarding_windows_cli_reports_errors(tmp_path: Path, capsys) -> None:
    exit_code = extract_onboarding_windows.main(
        ["--segment-manifest", str(tmp_path / "missing.json"), "--output-dir", str(tmp_path / "windows")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err
