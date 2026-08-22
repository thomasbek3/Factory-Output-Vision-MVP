"""Tests for the Track B StationPipeline (CP5)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.station_pipeline import (
    EXAM_GOLD_POSITIVES,
    TRAIN_MANIFEST_NAME,
    assert_no_truth_leakage_track_b,
    build_track_b_stages,
)
from app.services.onboarding_rehearsal import run_station


def make_args(tmp_path: Path) -> dict:
    return dict(
        station_id="pallet-a",
        video=tmp_path / "raw.mp4",
        calibration=tmp_path / "calibration.json",
        work_root=tmp_path / "work",
    )


def test_stage_chain_order_and_artifacts(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))
    names = [stage["name"] for stage in stages]
    # recall runs AFTER training (it measures candidates vs the sealed exam
    # key) and before the exam; label precedes train.
    assert names == ["mine", "extract", "label", "train", "recall", "exam"]
    for stage in stages:
        assert stage["artifact"]
        assert stage["command"][1].startswith("scripts/")


def test_exam_gold_is_sealed_key_never_train_manifest(tmp_path: Path) -> None:
    """Inverted leak assertion: exam/recall gold must be the sealed key; if it
    is ever the train manifest the build itself must fail."""
    stages = build_track_b_stages(**make_args(tmp_path))
    for name in ("recall", "exam"):
        stage = next(stage for stage in stages if stage["name"] == name)
        command = stage["command"]
        gold = command[command.index("--gold-positives") + 1]
        assert gold == str(EXAM_GOLD_POSITIVES)
        assert not gold.endswith(TRAIN_MANIFEST_NAME)
    # Train consumes ONLY the reviewed-labels manifest.
    train = next(stage for stage in stages if stage["name"] == "train")
    manifest = train["command"][train["command"].index("--manifest") + 1]
    assert manifest.endswith(TRAIN_MANIFEST_NAME)


def test_truth_leak_guard_rejects_train_manifest_as_gold(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))
    poisoned = [dict(stage) for stage in stages]
    exam = next(stage for stage in poisoned if stage["name"] == "exam")
    command = list(exam["command"])
    command[command.index("--gold-positives") + 1] = str(
        Path(command[command.index("--gold-positives") + 1]).parent / TRAIN_MANIFEST_NAME
    )
    exam["command"] = command
    with pytest.raises(AssertionError, match="TRUTH LEAK"):
        assert_no_truth_leakage_track_b(poisoned)


def test_truth_leak_guard_rejects_exam_key_in_training_lanes(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))
    poisoned = [dict(stage) for stage in stages]
    train = next(stage for stage in poisoned if stage["name"] == "train")
    command = list(train["command"])
    command[command.index("--manifest") + 1] = str(EXAM_GOLD_POSITIVES)
    train["command"] = command
    with pytest.raises(AssertionError, match="TRUTH LEAK"):
        assert_no_truth_leakage_track_b(poisoned)


def test_human_labeler_times_are_forwarded(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path), labeler="human", placement_times="10.5,44.2")
    label = next(stage for stage in stages if stage["name"] == "label")
    times_index = label["command"].index("--times")
    assert label["command"][times_index + 1] == "10.5,44.2"
    # And absent when not provided.
    plain = build_track_b_stages(**make_args(tmp_path), labeler="codex")
    codex_label = next(stage for stage in plain if stage["name"] == "label")
    assert "--times" not in codex_label["command"]


def test_run_station_executes_all_stages_with_fake_runner(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))

    def fake_runner(command):
        if "--out" in command:
            path = Path(command[command.index("--out") + 1])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        if "--manifest-out" in command:
            path = Path(command[command.index("--manifest-out") + 1])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]", encoding="utf-8")
        if "--out-dir" in command:
            path = Path(command[command.index("--out-dir") + 1])
            path.mkdir(parents=True, exist_ok=True)
            (path / "stack3_mobilenet.pt").write_bytes(b"stub")
        return type("Outcome", (), {"exit_code": 0, "stderr_tail": ""})()

    result = run_station(
        {"station_id": "pallet-a", "video": "x.mp4", "truth_ledger": ""},
        stages=stages,
        stage_runner=fake_runner,
    )
    assert result["failed_stage"] is None
    statuses = [stage["status"] for stage in result["stages"]]
    assert statuses == ["completed"] * len(stages)


def test_run_station_stops_on_first_failure(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))

    def failing_runner(_command):
        return type("Outcome", (), {"exit_code": 2, "stderr_tail": "boom"})()

    result = run_station(
        {"station_id": "pallet-a", "video": "x.mp4", "truth_ledger": ""},
        stages=stages,
        stage_runner=failing_runner,
    )
    assert result["failed_stage"] == "mine"
    assert result["stages"][1]["status"] == "not_run"


def test_exam_model_is_the_trained_student(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path), arch="stack3_mobilenet")
    train = next(stage for stage in stages if stage["name"] == "train")
    exam = next(stage for stage in stages if stage["name"] == "exam")
    command = exam["command"]
    model_arg = command[command.index("--model") + 1]
    assert model_arg == train["artifact"]


def test_stage_commands_reference_real_script_flags(tmp_path: Path) -> None:
    """Fabrication guard: every --flag we emit must exist in the target script."""
    stages = build_track_b_stages(**make_args(tmp_path), labeler="human", placement_times="1.0")
    script_flag_cache: dict[str, set[str]] = {}
    repo_root = Path(__file__).resolve().parents[1]
    for stage in stages:
        script_rel = stage["command"][1]
        if script_rel not in script_flag_cache:
            source = (repo_root / script_rel).read_text(encoding="utf-8")
            script_flag_cache[script_rel] = set(
                re.findall(r'add_argument\(\s*"(--[a-z-]+)"', source),
            )
        emitted = {
            token
            for index, token in enumerate(stage["command"])
            if token.startswith("--")
        }
        unknown = emitted - script_flag_cache[script_rel]
        assert not unknown, f"{script_rel}: flags {sorted(unknown)} do not exist"
