from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "factory-vision-yolo26-training-eval-v1"
Trainer = Callable[..., Path]
Evaluator = Callable[..., dict[str, Any]]


def run_yolo26_training_eval(
    *,
    data_yaml: Path,
    dataset_manifest: Path | None,
    base_model_path: Path,
    output_path: Path,
    train_project: Path,
    train_name: str,
    epochs: int = 25,
    imgsz: int = 640,
    batch: int = 8,
    device: str | None = None,
    confidence: float = 0.25,
    execute_training: bool = False,
    allow_model_download: bool = False,
    force: bool = False,
    trainer: Trainer | None = None,
    positive_evaluator: Evaluator | None = None,
    hard_negative_evaluator: Evaluator | None = None,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if imgsz <= 0:
        raise ValueError("imgsz must be positive")
    if batch <= 0:
        raise ValueError("batch must be positive")
    if not data_yaml.exists():
        raise FileNotFoundError(data_yaml)
    if dataset_manifest is not None and not dataset_manifest.exists():
        raise FileNotFoundError(dataset_manifest)
    if execute_training and not allow_model_download and not base_model_path.exists():
        raise FileNotFoundError(f"{base_model_path} does not exist; pass allow_model_download only for explicit downloads")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_family": "yolo26",
        "status": "dry_run" if not execute_training else "training_requested",
        "data_yaml": str(data_yaml),
        "dataset_manifest": str(dataset_manifest) if dataset_manifest else None,
        "base_model_path": str(base_model_path),
        "trained_model_path": None,
        "training": {
            "project": str(train_project),
            "name": train_name,
            "epochs": epochs,
            "imgsz": imgsz,
            "batch": batch,
            "device": device,
            "execute_training": execute_training,
            "allow_model_download": allow_model_download,
        },
        "eval_reports": {
            "positives": None,
            "hard_negatives": None,
        },
        "promotion_allowed": False,
        "requires_blind_replay_gate": True,
        "refuses_validation_truth": True,
    }
    if not execute_training:
        _write_json(output_path, report)
        return report

    train = trainer or _train_with_ultralytics
    trained_model_path = train(
        data_yaml=data_yaml,
        base_model_path=base_model_path,
        train_project=train_project,
        train_name=train_name,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
    )
    positive_output = output_path.parent / f"{output_path.stem}.positive_eval.json"
    hard_negative_output = output_path.parent / f"{output_path.stem}.hard_negative_eval.json"
    positive_eval = positive_evaluator or _evaluate_positives
    hard_negative_eval = hard_negative_evaluator or _evaluate_hard_negatives
    positives_report = positive_eval(
        data_yaml=data_yaml,
        dataset_manifest=dataset_manifest,
        model_path=trained_model_path,
        output_path=positive_output,
        confidence=confidence,
        force=True,
    )
    hard_negative_report = hard_negative_eval(
        data_yaml=data_yaml,
        dataset_manifest=dataset_manifest,
        model_path=trained_model_path,
        output_path=hard_negative_output,
        confidence=confidence,
        force=True,
    )
    report["status"] = "trained_and_evaluated"
    report["trained_model_path"] = str(trained_model_path)
    report["eval_reports"] = {
        "positives": str(positive_output),
        "hard_negatives": str(hard_negative_output),
    }
    report["summary"] = {
        "positive_eval_schema": positives_report.get("schema_version"),
        "hard_negative_eval_schema": hard_negative_report.get("schema_version"),
        "matched_positive_labels": (positives_report.get("summary") or {}).get("matched_labels"),
        "hard_negative_false_positive_detections": (hard_negative_report.get("summary") or {}).get(
            "false_positive_detections"
        ),
    }
    _write_json(output_path, report)
    return report


def _train_with_ultralytics(
    *,
    data_yaml: Path,
    base_model_path: Path,
    train_project: Path,
    train_name: str,
    epochs: int,
    imgsz: int,
    batch: int,
    device: str | None,
) -> Path:
    from ultralytics import YOLO

    model = YOLO(str(base_model_path))
    kwargs: dict[str, Any] = {
        "data": str(data_yaml),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "project": str(train_project),
        "name": train_name,
        "exist_ok": True,
    }
    if device:
        kwargs["device"] = device
    result = model.train(**kwargs)
    save_dir = Path(str(getattr(result, "save_dir", train_project / train_name)))
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(best)
    return best


def _evaluate_positives(**kwargs: Any) -> dict[str, Any]:
    from scripts.eval_detector_positives import evaluate_detector_positives

    return evaluate_detector_positives(**kwargs)


def _evaluate_hard_negatives(**kwargs: Any) -> dict[str, Any]:
    from scripts.eval_detector_false_positives import evaluate_false_positives

    return evaluate_false_positives(**kwargs)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
