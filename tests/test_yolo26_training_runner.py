from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.yolo26_training_runner import SCHEMA_VERSION, run_yolo26_training_eval
from scripts.research.factory2 import run_yolo26_training_eval as run_yolo26_training_eval_cli


def _write_data_yaml(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "path: .",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: active_panel",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _fake_trainer(**kwargs) -> Path:
    best = Path(kwargs["train_project"]) / kwargs["train_name"] / "weights" / "best.pt"
    best.parent.mkdir(parents=True, exist_ok=True)
    best.write_bytes(b"fake-model")
    return best


def _fake_positive_eval(**kwargs) -> dict:
    output = Path(kwargs["output_path"])
    payload = {
        "schema_version": "active-panel-positive-detector-eval-v1",
        "summary": {"matched_labels": 3, "total_labels": 3},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _fake_hard_negative_eval(**kwargs) -> dict:
    output = Path(kwargs["output_path"])
    payload = {
        "schema_version": "active-panel-false-positive-eval-v1",
        "summary": {"false_positive_detections": 0, "hard_negative_images": 2},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_yolo26_training_eval_dry_run_writes_non_promotion_report(tmp_path: Path) -> None:
    data_yaml = tmp_path / "data.yaml"
    output = tmp_path / "report.json"
    _write_data_yaml(data_yaml)

    report = run_yolo26_training_eval(
        data_yaml=data_yaml,
        dataset_manifest=None,
        base_model_path=tmp_path / "missing-yolo26n.pt",
        output_path=output,
        train_project=tmp_path / "runs",
        train_name="dry",
        execute_training=False,
    )

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "dry_run"
    assert report["promotion_allowed"] is False
    assert report["requires_blind_replay_gate"] is True
    assert report["refuses_validation_truth"] is True
    assert json.loads(output.read_text())["status"] == "dry_run"


def test_yolo26_training_eval_runs_fake_train_and_eval_reports(tmp_path: Path) -> None:
    data_yaml = tmp_path / "data.yaml"
    dataset_manifest = tmp_path / "dataset_manifest.json"
    base_model = tmp_path / "yolo26n.pt"
    output = tmp_path / "report.json"
    _write_data_yaml(data_yaml)
    dataset_manifest.write_text(json.dumps({"schema_version": "active-panel-yolo-dataset-v1", "items": []}))
    base_model.write_bytes(b"base-model")

    report = run_yolo26_training_eval(
        data_yaml=data_yaml,
        dataset_manifest=dataset_manifest,
        base_model_path=base_model,
        output_path=output,
        train_project=tmp_path / "runs",
        train_name="station",
        execute_training=True,
        force=True,
        trainer=_fake_trainer,
        positive_evaluator=_fake_positive_eval,
        hard_negative_evaluator=_fake_hard_negative_eval,
    )

    assert report["status"] == "trained_and_evaluated"
    assert Path(report["trained_model_path"]).exists()
    assert Path(report["eval_reports"]["positives"]).exists()
    assert Path(report["eval_reports"]["hard_negatives"]).exists()
    assert report["summary"]["matched_positive_labels"] == 3
    assert report["summary"]["hard_negative_false_positive_detections"] == 0
    assert report["promotion_allowed"] is False


def test_yolo26_training_eval_requires_existing_base_model_for_execution(tmp_path: Path) -> None:
    data_yaml = tmp_path / "data.yaml"
    _write_data_yaml(data_yaml)

    with pytest.raises(FileNotFoundError, match="allow_model_download"):
        run_yolo26_training_eval(
            data_yaml=data_yaml,
            dataset_manifest=None,
            base_model_path=tmp_path / "missing-yolo26n.pt",
            output_path=tmp_path / "report.json",
            train_project=tmp_path / "runs",
            train_name="station",
            execute_training=True,
        )


def test_run_yolo26_training_eval_cli_dry_run(tmp_path: Path, capsys) -> None:
    data_yaml = tmp_path / "data.yaml"
    output = tmp_path / "report.json"
    _write_data_yaml(data_yaml)

    exit_code = run_yolo26_training_eval_cli.main(
        ["--data-yaml", str(data_yaml), "--output", str(output), "--force"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "dry_run"' in captured.out
    assert json.loads(output.read_text())["requires_blind_replay_gate"] is True
