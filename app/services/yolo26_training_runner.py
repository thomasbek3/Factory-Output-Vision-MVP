from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.services.training_exam_guard import (
    DEFAULT_EXAM_FIREWALL_PATH,
    DEFAULT_SOURCE_SET_REGISTRY_PATH,
    validate_training_manifest,
)


SCHEMA_VERSION = "factory-vision-yolo26-training-eval-v1"
DATASET_SCHEMA_VERSION = "active-panel-yolo-dataset-v1"
YOLO_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
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
    exam_firewall_path: Path = DEFAULT_EXAM_FIREWALL_PATH,
    source_set_registry_path: Path = DEFAULT_SOURCE_SET_REGISTRY_PATH,
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
    if execute_training and dataset_manifest is None:
        raise ValueError("dataset_manifest is required for training")
    if execute_training and not allow_model_download and not base_model_path.exists():
        raise FileNotFoundError(f"{base_model_path} does not exist; pass allow_model_download only for explicit downloads")

    firewall_validated = False
    if dataset_manifest is not None:
        try:
            manifest_payload = json.loads(dataset_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("dataset manifest is unavailable or invalid; training must fail closed") from exc
        validate_training_manifest(
            manifest_payload,
            exam_firewall_path=exam_firewall_path,
            source_set_registry_path=source_set_registry_path,
        )
        _validate_yolo_dataset_binding(
            manifest=manifest_payload,
            manifest_path=dataset_manifest,
            data_yaml=data_yaml,
        )
        firewall_validated = True

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
        "training_firewall_validated": firewall_validated,
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


def _validate_yolo_dataset_binding(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    data_yaml: Path,
) -> None:
    if manifest.get("schema_version") != DATASET_SCHEMA_VERSION:
        raise ValueError(f"dataset manifest schema_version must be {DATASET_SCHEMA_VERSION}")

    samples = manifest.get("samples")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("dataset manifest items must be a non-empty list")
    if items != samples:
        raise ValueError("dataset manifest items must exactly match validated samples")

    declared_data_yaml = manifest.get("data_yaml_path")
    if not isinstance(declared_data_yaml, str) or not declared_data_yaml.strip():
        raise ValueError("dataset manifest data_yaml_path is required")
    declared_path = Path(declared_data_yaml).expanduser()
    if not declared_path.is_absolute():
        declared_path = manifest_path.parent / declared_path
    if declared_path.resolve() != data_yaml.resolve():
        raise ValueError("dataset manifest does not describe the requested data_yaml")

    yaml_paths = _parse_yolo_data_paths(data_yaml)
    dataset_root = (data_yaml.parent / yaml_paths["path"]).resolve()
    allowed_pairs = {
        split: (
            (dataset_root / yaml_paths[split]).resolve(),
            (dataset_root / yaml_paths[split].replace("images", "labels", 1)).resolve(),
        )
        for split in ("train", "val")
    }
    manifest_images: set[Path] = set()
    manifest_labels: set[Path] = set()
    for item in items:
        split = item.get("split")
        if split not in allowed_pairs:
            raise ValueError("dataset manifest item split must be train or val")
        image_path = _required_existing_path(item, "image_path")
        label_path = _required_existing_path(item, "label_path")
        image_root, label_root = allowed_pairs[split]
        if not _is_relative_to(image_path, image_root):
            raise ValueError("dataset manifest image_path is outside the requested data_yaml split")
        if not _is_relative_to(label_path, label_root):
            raise ValueError("dataset manifest label_path is outside the requested data_yaml split")
        manifest_images.add(image_path)
        manifest_labels.add(label_path)

    yaml_images = {
        path.resolve()
        for image_root, _ in allowed_pairs.values()
        if image_root.is_dir()
        for path in image_root.rglob("*")
        if path.is_file() and path.suffix.lower() in YOLO_IMAGE_SUFFIXES
    }
    yaml_labels = {
        path.resolve()
        for _, label_root in allowed_pairs.values()
        if label_root.is_dir()
        for path in label_root.rglob("*.txt")
        if path.is_file()
    }
    if manifest_images != yaml_images or manifest_labels != yaml_labels:
        raise ValueError("dataset manifest must exactly inventory every data_yaml image and label")


def _parse_yolo_data_paths(data_yaml: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in data_yaml.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line[0].isspace() or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        if key in {"path", "train", "val"}:
            payload[key] = value.strip().strip("\"'")
    if not all(payload.get(key) for key in ("path", "train", "val")):
        raise ValueError("data_yaml must declare path, train, and val")
    return payload


def _required_existing_path(item: dict[str, Any], key: str) -> Path:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"dataset manifest item {key} is required")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"dataset manifest item {key} is unavailable")
    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


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
