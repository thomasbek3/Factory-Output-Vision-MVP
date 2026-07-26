from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.yolo26_training_runner import SCHEMA_VERSION, run_yolo26_training_eval
from app.services.training_exam_guard import sha256_file
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


def _write_training_manifest(tmp_path: Path, data_yaml: Path) -> Path:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"ordinary-training-source")
    source_hash = sha256_file(source)
    image = tmp_path / "images" / "train" / "sample.jpg"
    label = tmp_path / "labels" / "train" / "sample.txt"
    image.parent.mkdir(parents=True, exist_ok=True)
    label.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"image")
    label.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    sample = {
        "kind": "positive",
        "split": "train",
        "image_path": str(image),
        "label_path": str(label),
        "training_eligible": True,
        "source": str(source),
        "source_sha256": source_hash,
        "lineage_source_sha256": [source_hash],
        "lineage_is_transitive_complete": True,
        "start_at": "2026-07-25T12:00:00Z",
        "end_at": "2026-07-25T12:01:00Z",
    }
    path = tmp_path / "dataset_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "active-panel-yolo-dataset-v1",
                "data_yaml_path": str(data_yaml),
                "items": [sample],
                "samples": [sample],
            }
        ),
        encoding="utf-8",
    )
    return path


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
    dataset_manifest = _write_training_manifest(tmp_path, data_yaml)
    base_model = tmp_path / "yolo26n.pt"
    output = tmp_path / "report.json"
    _write_data_yaml(data_yaml)
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
    assert report["training_firewall_validated"] is True


def test_yolo26_training_refuses_exam_source_before_trainer_runs(tmp_path: Path) -> None:
    data_yaml = tmp_path / "data.yaml"
    source = tmp_path / "exam-source.mp4"
    source.write_bytes(b"protected-exam-source")
    source_hash = sha256_file(source)
    image = tmp_path / "images" / "train" / "sample.jpg"
    label = tmp_path / "labels" / "train" / "sample.txt"
    image.parent.mkdir(parents=True, exist_ok=True)
    label.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"image")
    label.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    sample = {
        "kind": "positive",
        "split": "train",
        "image_path": str(image),
        "label_path": str(label),
        "training_eligible": True,
        "source": str(source),
        "source_sha256": source_hash,
        "lineage_source_sha256": [source_hash],
        "lineage_is_transitive_complete": True,
        "start_at": "2026-07-25T12:00:00Z",
        "end_at": "2026-07-25T12:01:00Z",
    }
    dataset_manifest = tmp_path / "dataset_manifest.json"
    dataset_manifest.write_text(
        json.dumps(
            {
                "schema_version": "active-panel-yolo-dataset-v1",
                "data_yaml_path": str(data_yaml),
                "items": [sample],
                "samples": [sample],
            }
        ),
        encoding="utf-8",
    )
    exam_path = tmp_path / "exam.json"
    exam_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-exam-firewall-v2",
                "station_id": "line-a",
                "fail_closed": True,
                "intervals": [
                    {
                        "id": "exam-1",
                        "source_sha256": source_hash,
                        "lineage_source_sha256": [source_hash],
                        "lineage_is_transitive_complete": True,
                        "start_at": "2026-07-25T12:00:00Z",
                        "end_at": "2026-07-25T12:01:00Z",
                        "training_eligible": False,
                        "assignment_eligible": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    source_sets_path = tmp_path / "source_sets.json"
    source_sets_path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-review-source-sets-v1",
                "fail_closed": True,
                "sets": {
                    "resolver_calibration": [],
                    "ai_evaluation_holdout": [
                        {
                            "source_sha256": source_hash,
                            "lineage_source_sha256": [source_hash],
                            "lineage_is_transitive_complete": True,
                            "start_at": "2026-07-25T12:00:00Z",
                            "end_at": "2026-07-25T12:01:00Z",
                        }
                    ],
                    "practice": [],
                    "qualification": [],
                },
            }
        ),
        encoding="utf-8",
    )
    _write_data_yaml(data_yaml)
    trainer_called = False

    def forbidden_trainer(**kwargs) -> Path:
        nonlocal trainer_called
        trainer_called = True
        return _fake_trainer(**kwargs)

    with pytest.raises(ValueError, match="protected source-set"):
        run_yolo26_training_eval(
            data_yaml=data_yaml,
            dataset_manifest=dataset_manifest,
            base_model_path=source,
            output_path=tmp_path / "report.json",
            train_project=tmp_path / "runs",
            train_name="blocked",
            execute_training=True,
            trainer=forbidden_trainer,
            exam_firewall_path=exam_path,
            source_set_registry_path=source_sets_path,
        )

    assert trainer_called is False


def test_yolo26_training_eval_requires_existing_base_model_for_execution(tmp_path: Path) -> None:
    data_yaml = tmp_path / "data.yaml"
    dataset_manifest = _write_training_manifest(tmp_path, data_yaml)
    _write_data_yaml(data_yaml)

    with pytest.raises(FileNotFoundError, match="allow_model_download"):
        run_yolo26_training_eval(
            data_yaml=data_yaml,
            dataset_manifest=dataset_manifest,
            base_model_path=tmp_path / "missing-yolo26n.pt",
            output_path=tmp_path / "report.json",
            train_project=tmp_path / "runs",
            train_name="station",
            execute_training=True,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload, _: payload.update({"items": []}), "items must be a non-empty"),
        (
            lambda payload, _: payload["items"][0].update({"label_path": "/tmp/not-the-reviewed-label.txt"}),
            "items must exactly match",
        ),
        (
            lambda payload, tmp_path: payload.update({"data_yaml_path": str(tmp_path / "other.yaml")}),
            "does not describe",
        ),
        (
            lambda payload, tmp_path: (
                (tmp_path / "images" / "train" / "unreviewed.jpg").write_bytes(b"unreviewed"),
                (tmp_path / "labels" / "train" / "unreviewed.txt").write_text("", encoding="utf-8"),
            ),
            "exactly inventory",
        ),
    ],
)
def test_yolo26_training_refuses_unbound_manifest_before_trainer_runs(
    tmp_path: Path,
    mutate,
    message: str,
) -> None:
    data_yaml = tmp_path / "data.yaml"
    _write_data_yaml(data_yaml)
    dataset_manifest = _write_training_manifest(tmp_path, data_yaml)
    payload = json.loads(dataset_manifest.read_text(encoding="utf-8"))
    mutate(payload, tmp_path)
    dataset_manifest.write_text(json.dumps(payload), encoding="utf-8")
    trainer_called = False

    def forbidden_trainer(**kwargs) -> Path:
        nonlocal trainer_called
        trainer_called = True
        return _fake_trainer(**kwargs)

    with pytest.raises(ValueError, match=message):
        run_yolo26_training_eval(
            data_yaml=data_yaml,
            dataset_manifest=dataset_manifest,
            base_model_path=tmp_path / "source.mp4",
            output_path=tmp_path / "report.json",
            train_project=tmp_path / "runs",
            train_name="blocked",
            execute_training=True,
            trainer=forbidden_trainer,
        )

    assert trainer_called is False


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
