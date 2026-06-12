from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.onboarding_rehearsal import (
    StageOutcome,
    assert_no_truth_leakage,
    build_station_stages,
    evaluate_train_gate,
    run_station,
)

STATION = {
    "station_id": "factory2_auto",
    "video": "/archive/videos/raw/factory2.MOV",
    "truth_ledger": "data/reports/factory2_human_truth_ledger.v1.json",
    "baseline_case_id": "factory2_test_case_1",
}


def _stages(tmp_path: Path, **overrides):
    kwargs = dict(
        work_root=tmp_path,
        playback_speed=8.0,
        teacher_provider="codex_cli",
        allow_cloud=True,
        teacher_batch_size=4,
        box_backend="diff_box",
        base_model=Path("yolov8n.pt"),
        epochs=40,
        device="mps",
    )
    kwargs.update(overrides)
    return build_station_stages(STATION, **kwargs)


def test_stage_chain_order_and_artifacts(tmp_path: Path) -> None:
    stages = _stages(tmp_path)
    names = [stage["name"] for stage in stages]
    assert names == [
        "split",
        "segments",
        "proposals",
        "packets",
        "teacher",
        "reconcile",
        "fuse",
        "boxes",
        "review",
        "calibration",
        "negatives",
        "dataset",
        "train",
        "publish",
        "gate",
        "grade",
    ]
    mining_names = [stage["name"] for stage in _stages(tmp_path, enable_mining=True)]
    assert mining_names[12:16] == ["train", "mine", "dataset2", "train2"]
    teacher = next(stage for stage in stages if stage["name"] == "teacher")
    assert "--allow-cloud" in teacher["command"]
    train = next(stage for stage in stages if stage["name"] == "train")
    assert "--execute-training" in train["command"]
    gate = next(stage for stage in stages if stage["name"] == "gate")
    assert "--execute" in gate["command"]
    # the holdout manifest authored at split time points at the future trained model path
    split = next(stage for stage in stages if stage["name"] == "split")
    model_arg = split["command"][split["command"].index("--model-path") + 1]
    assert model_arg.endswith("train/model/weights/best.pt")


def test_truth_leakage_assertion_passes_for_built_chain(tmp_path: Path) -> None:
    stages = _stages(tmp_path)
    assert_no_truth_leakage(stages, truth_ledger=STATION["truth_ledger"])


def test_truth_leakage_assertion_catches_violation(tmp_path: Path) -> None:
    stages = _stages(tmp_path)
    teacher = next(stage for stage in stages if stage["name"] == "teacher")
    teacher["command"].extend(["--secret-hint", STATION["truth_ledger"]])
    with pytest.raises(ValueError, match="truth leakage"):
        assert_no_truth_leakage(stages, truth_ledger=STATION["truth_ledger"])


def test_run_station_skips_existing_and_stops_on_failure(tmp_path: Path) -> None:
    stages = _stages(tmp_path)
    # pretend split already ran
    split_artifact = Path(stages[0]["artifact"])
    split_artifact.parent.mkdir(parents=True, exist_ok=True)
    split_artifact.write_text("{}", encoding="utf-8")

    calls: list[str] = []

    def runner(command: list[str]) -> StageOutcome:
        name = command[1]
        calls.append(name)
        if "propose_onboarding_events" in name:
            return StageOutcome(exit_code=1, stderr_tail="boom")
        return StageOutcome(exit_code=0)

    run = run_station(STATION, stages=stages, stage_runner=runner)
    statuses = {stage["name"]: stage["status"] for stage in run["stages"]}
    assert statuses["split"] == "skipped_existing"
    assert statuses["segments"] == "completed"
    assert statuses["proposals"] == "failed"
    assert statuses["teacher"] == "not_run"
    assert run["failed_stage"] == "proposals"
    assert len(calls) == 2  # segments + proposals only


def test_force_stage_reruns_existing_artifact(tmp_path: Path) -> None:
    stages = _stages(tmp_path)[:1]
    artifact = Path(stages[0]["artifact"])
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}", encoding="utf-8")

    calls: list[str] = []

    def runner(command: list[str]) -> StageOutcome:
        calls.append(command[1])
        return StageOutcome(exit_code=0)

    run = run_station(STATION, stages=stages, stage_runner=runner, force_stages={"split"})
    assert run["stages"][0]["status"] == "completed"
    assert len(calls) == 1


def test_train_retries_on_cpu_after_mps_failure(tmp_path: Path) -> None:
    stages = [stage for stage in _stages(tmp_path) if stage["name"] == "train"]
    attempts: list[str] = []

    def runner(command: list[str]) -> StageOutcome:
        device = command[command.index("--device") + 1]
        attempts.append(device)
        return StageOutcome(exit_code=1 if device == "mps" else 0, stderr_tail="mps blew up")

    run = run_station(STATION, stages=stages, stage_runner=runner, device="mps")
    assert attempts == ["mps", "cpu"]
    assert run["stages"][0]["status"] == "completed"


def test_train_gate_math() -> None:
    report = {"summary": {"matched_positive_labels": 18, "hard_negative_false_positive_detections": 0}}
    dataset = {"summary": {"positive_count": 20}}
    gate = evaluate_train_gate(report, dataset, min_positive_ratio=0.8, max_hard_negative_false_positives=0)
    assert gate["passed"] is True
    assert gate["matched_positive_ratio"] == 0.9

    weak = {"summary": {"matched_positive_labels": 10, "hard_negative_false_positive_detections": 0}}
    gate = evaluate_train_gate(weak, dataset, min_positive_ratio=0.8, max_hard_negative_false_positives=0)
    assert gate["passed"] is False

    leaky = {"summary": {"matched_positive_labels": 20, "hard_negative_false_positive_detections": 3}}
    gate = evaluate_train_gate(leaky, dataset, min_positive_ratio=0.8, max_hard_negative_false_positives=0)
    assert gate["passed"] is False

    gate = evaluate_train_gate(None, None, min_positive_ratio=0.8, max_hard_negative_false_positives=0)
    assert gate["passed"] is False
