"""Tests for the Track B StationPipeline (CP5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.station_pipeline import (
    TRACK_B_TRUTH_TOUCHING_STAGES,
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
    assert names == ["mine", "recall", "extract", "label", "train", "exam"]
    # Every stage declares its artifact; commands reference the venv python.
    for stage in stages:
        assert stage["artifact"]
        assert stage["command"][1].startswith("scripts/")
    # The exam consumes reviewed placements (promotion truth), not raw candidates.
    exam = stages[-1]["command"]
    gold_index = exam.index("--gold-positives")
    assert exam[gold_index + 1].endswith("reviewed_labels.json")


def test_truth_touching_stages_subset_of_guard() -> None:
    # label/exam touch promotion truth; both must be recognized by the guard.
    assert {"label", "exam"} <= TRACK_B_TRUTH_TOUCHING_STAGES


def test_exam_uses_trained_student_model(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path), arch="stack3_mobilenet")
    train = next(stage for stage in stages if stage["name"] == "train")
    exam = next(stage for stage in stages if stage["name"] == "exam")
    command = exam["command"]
    model_arg = command[command.index("--model") + 1]
    assert model_arg == train["artifact"]


def test_run_station_executes_all_stages_with_fake_runner(tmp_path: Path) -> None:
    stages = build_track_b_stages(**make_args(tmp_path))

    def fake_runner(command):
        # Materialize each declared artifact so the executor sees success.
        out_index = command.index("--out") if "--out" in command else None
        if out_index is not None:
            Path(command[out_index + 1]).parent.mkdir(parents=True, exist_ok=True)
            Path(command[out_index + 1]).write_text("{}", encoding="utf-8")
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


def test_stage_commands_reference_real_script_flags(tmp_path: Path) -> None:
    """Fabrication guard: every --flag we emit must exist in the target script."""
    import re

    stages = build_track_b_stages(**make_args(tmp_path))
    script_flag_cache: dict[str, set[str]] = {}
    for stage in stages:
        script_rel = stage["command"][1]
        if script_rel not in script_flag_cache:
            source = (Path(__file__).resolve().parents[1] / script_rel).read_text(encoding="utf-8")
            script_flag_cache[script_rel] = set(
                re.findall(r'add_argument\(\s*"(--[a-z-]+)"', source),
            )
        emitted = {
            token
            for index, token in enumerate(stage["command"])
            if token.startswith("--") and index + 1 < len(stage["command"]) and not stage["command"][index + 1].startswith("-")
        }
        unknown = emitted - script_flag_cache[script_rel]
        assert not unknown, f"{script_rel}: flags {sorted(unknown)} do not exist"
