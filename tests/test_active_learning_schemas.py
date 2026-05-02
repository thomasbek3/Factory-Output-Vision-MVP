from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.extract_event_windows import build_event_evidence, write_review_frames_for_evidence


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_required(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    for key in schema.get("required", []):
        assert key in payload, f"missing required key {key}"


def _write_observed_events(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-app-run-v1",
                "observed_event_count": 2,
                "current_state": "DEMO_COMPLETE",
                "run_complete": True,
                "observed_coverage_end_sec": 20.0,
                "events": [
                    {
                        "event_ts": 5.0,
                        "runtime_total_after_event": 1,
                        "reader_frame_sequence_index": 50,
                        "reason": "dead_track_event",
                    },
                    {
                        "event_ts": 15.0,
                        "runtime_total_after_event": 2,
                        "reader_frame_sequence_index": 150,
                        "reason": "end_of_stream_active_track_event",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_active_learning_schema_files_are_present() -> None:
    for name in (
        "event_evidence.schema.json",
        "teacher_label.schema.json",
        "review_label.schema.json",
        "active_learning_dataset.schema.json",
    ):
        schema = _read_json(REPO_ROOT / "validation/schemas" / name)
        assert schema["type"] == "object"
        assert schema["required"]


def test_extract_event_windows_produces_stable_schema_shaped_evidence(tmp_path: Path) -> None:
    observed_path = tmp_path / "observed.json"
    video_path = tmp_path / "video.mov"
    _write_observed_events(observed_path)
    video_path.write_bytes(b"fixture-video")

    first = build_event_evidence(
        case_id="fixture_case",
        manifest_path=None,
        observed_events_path=observed_path,
        video_path=video_path,
        video_sha256=None,
        privacy_mode="offline_local",
        window_before_sec=1.0,
        window_after_sec=1.5,
        include_negatives=True,
        negative_count=1,
        negative_window_sec=2.0,
    )
    second = build_event_evidence(
        case_id="fixture_case",
        manifest_path=None,
        observed_events_path=observed_path,
        video_path=video_path,
        video_sha256=None,
        privacy_mode="offline_local",
        window_before_sec=1.0,
        window_after_sec=1.5,
        include_negatives=True,
        negative_count=1,
        negative_window_sec=2.0,
    )

    assert first == second
    schema = _read_json(REPO_ROOT / "validation/schemas/event_evidence.schema.json")
    _assert_required(first, schema)
    assert first["schema_version"] == "factory-vision-event-evidence-v1"
    assert first["privacy_mode"] == "offline_local"
    assert first["video"]["sha256"]
    assert [window["window_id"] for window in first["windows"]] == [
        "fixture_case-count-0001",
        "fixture_case-count-0002",
        "fixture_case-negative-0001",
    ]
    assert first["windows"][0]["label_authority_tier"] == "bronze"
    assert first["review_window_metadata"][0]["review_status"] == "not_reviewed"


def test_write_review_frames_for_evidence_adds_frame_assets(tmp_path: Path) -> None:
    evidence = {
        "schema_version": "factory-vision-event-evidence-v1",
        "case_id": "fixture_case",
        "privacy_mode": "offline_local",
        "video": {"path": "video.mov", "sha256": "abc"},
        "source_artifacts": {"observed_events_path": "observed.json"},
        "model_settings": {},
        "windows": [
            {
                "window_id": "fixture-window-1",
                "window_type": "count_event",
                "time_window": {"start_sec": 1.0, "center_sec": 2.0, "end_sec": 3.0},
                "frame_window": {},
                "count_event_evidence": {"event_ts": 2.0},
                "review_window": {
                    "sample_timestamps_sec": [1.0, 2.0, 3.0],
                    "asset_status": "metadata_only",
                },
                "confidence_tier": "unknown",
                "duplicate_risk": "unknown",
                "miss_risk": "unknown",
                "label_authority_tier": "bronze",
            }
        ],
        "review_window_metadata": [],
    }

    def fake_reader(video_path: Path, timestamp_sec: float) -> bytes:
        assert video_path == tmp_path / "video.mov"
        return f"frame-{timestamp_sec}".encode("utf-8")

    def fake_writer(path: Path, frame: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(frame)

    updated = write_review_frames_for_evidence(
        evidence=evidence,
        video_path=tmp_path / "video.mov",
        frame_output_dir=tmp_path / "frames",
        force=True,
        frame_reader=fake_reader,
        frame_writer=fake_writer,
    )

    review_window = updated["windows"][0]["review_window"]
    assert review_window["asset_status"] == "frames_extracted"
    assert len(review_window["frame_assets"]) == 3
    for asset in review_window["frame_assets"]:
        assert Path(asset["frame_path"]).exists()
        assert asset["status"] == "written"
        assert asset["sha256"]
