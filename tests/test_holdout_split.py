from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.holdout_split import (
    STANDARD_EVENT_PARAMS,
    author_holdout_case_manifest,
    compute_holdout_split,
    derive_holdout_truth_ledger,
)
from scripts.validate_video import build_launch_command
from scripts.validation_truth_guard import validate_truth_payload


KEYFRAMES = [float(value) for value in range(0, 1000, 10)]  # every 10s


def test_split_honors_keyframes_and_fraction() -> None:
    split = compute_holdout_split(
        duration_sec=1000.0,
        truth_event_timestamps=[100.0, 200.0, 800.0, 850.0, 900.0],
        keyframes=KEYFRAMES,
        train_fraction=0.7,
    )
    assert split["split_sec"] == 700.0  # keyframe at the exact 70% point
    assert split["adjusted"] is False
    assert split["holdout_truth_event_count"] == 3


def test_split_walks_earlier_when_holdout_too_thin() -> None:
    split = compute_holdout_split(
        duration_sec=1000.0,
        truth_event_timestamps=[100.0, 200.0, 300.0, 400.0, 500.0],
        keyframes=KEYFRAMES,
        train_fraction=0.7,
    )
    # needs 3 events in holdout -> split must be <= 300 - margin, snapped to a keyframe
    assert split["split_sec"] <= 295.0
    assert split["adjusted"] is True
    assert split["holdout_truth_event_count"] >= 3


def test_split_never_cuts_through_an_event() -> None:
    split = compute_holdout_split(
        duration_sec=1000.0,
        truth_event_timestamps=[200.0, 400.0, 699.0, 800.0, 900.0],
        keyframes=KEYFRAMES,
        train_fraction=0.7,
    )
    for event_ts in (699.0,):
        assert not (abs(event_ts - split["split_sec"]) < 5.0)
    assert split["adjusted"] is True


def test_derived_ledger_shifts_and_renumbers(tmp_path: Path) -> None:
    source = tmp_path / "truth.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "human-truth-ledger-v1",
                "counting_rule": "count placements",
                "events": [
                    {"truth_event_id": "t-1", "event_ts": 100.0, "count_total": 1},
                    {"truth_event_id": "t-2", "event_ts": 750.0, "count_total": 2},
                    {"truth_event_id": "t-3", "event_ts": 900.0, "count_total": 3},
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "holdout_truth.json"
    ledger = derive_holdout_truth_ledger(source_ledger_path=source, split_sec=700.0, output_path=output)

    assert ledger["expected_human_total"] == 2
    assert [event["event_ts"] for event in ledger["events"]] == [50.0, 200.0]
    assert [event["count_total"] for event in ledger["events"]] == [1, 2]
    assert ledger["counting_rule"] == "count placements"
    validate_truth_payload(ledger)  # must be eligible as gate-compare truth

    with pytest.raises(FileExistsError):
        derive_holdout_truth_ledger(source_ledger_path=source, split_sec=700.0, output_path=output)


def test_authored_manifest_drives_launch_command_with_standard_params(tmp_path: Path, monkeypatch) -> None:
    import app.services.holdout_split as holdout_split

    monkeypatch.setattr(
        holdout_split,
        "probe_video",
        lambda path, **kwargs: {
            "path": str(path),
            "duration_sec": 300.0,
            "width": 1920,
            "height": 1080,
            "codec": "hevc",
        },
    )
    monkeypatch.setattr(holdout_split, "sha256_file", lambda path: "deadbeef")

    clip = tmp_path / "station_holdout.MOV"
    clip.write_bytes(b"fake video")
    ledger_path = tmp_path / "holdout_truth.json"
    derived_ledger = {"expected_human_total": 4, "counting_rule": "count placements"}
    manifest = author_holdout_case_manifest(
        station_id="factory2_auto",
        holdout_clip_path=clip,
        derived_ledger=derived_ledger,
        derived_ledger_path=ledger_path,
        model_path=tmp_path / "auto_model.pt",
        playback_speed=8.0,
        output_path=tmp_path / "case.json",
    )

    assert manifest["schema_version"] == "factory-vision-video-manifest-v1"
    assert manifest["truth"]["expected_total"] == 4
    assert manifest["runtime"]["yolo_confidence"] == STANDARD_EVENT_PARAMS["yolo_confidence"]
    assert manifest["promotion_status"] == "not_promoted"

    command = build_launch_command(manifest)
    joined = " ".join(command)
    assert "--no-runtime-calibration" in joined
    assert "--playback-speed 8" in joined
    assert "--model" in joined and "auto_model.pt" in joined
    assert "--event-track-max-age 30" in joined
    assert "--event-track-min-frames 8" in joined
    assert "--event-detection-cluster-distance 150" in joined
    assert "--yolo-confidence 0.25" in joined
