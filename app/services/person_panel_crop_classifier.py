"""Second-stage crop classifier for carried-panel versus worker-only evidence."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_MODEL_PATH = Path("models/factory2_person_panel_binary_manual_v1.pt")


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def summarize_predictions(
    predictions: list[dict[str, Any]],
    *,
    min_positive_crops: int = 1,
    min_positive_ratio: float = 0.75,
    min_positive_confidence: float = 0.95,
    min_negative_crops: int = 1,
    min_negative_ratio: float = 0.75,
    min_negative_confidence: float = 0.95,
) -> dict[str, Any]:
    total = len(predictions)
    label_counts: dict[str, int] = {}
    label_max_confidence: dict[str, float] = {}
    for item in predictions:
        label = str(item.get("label") or "unknown")
        confidence = float(item.get("confidence") or 0.0)
        label_counts[label] = label_counts.get(label, 0) + 1
        label_max_confidence[label] = max(label_max_confidence.get(label, 0.0), confidence)

    carried_count = label_counts.get("carried_panel", 0)
    worker_count = label_counts.get("worker_only", 0)
    carried_ratio = carried_count / total if total else 0.0
    worker_ratio = worker_count / total if total else 0.0
    carried_confidence = label_max_confidence.get("carried_panel", 0.0)
    worker_confidence = label_max_confidence.get("worker_only", 0.0)

    recommendation = "insufficient_visibility"
    if (
        carried_count >= min_positive_crops
        and carried_ratio >= min_positive_ratio
        and carried_confidence >= min_positive_confidence
    ):
        recommendation = "carried_panel"
    elif (
        worker_count >= min_negative_crops
        and worker_ratio >= min_negative_ratio
        and worker_confidence >= min_negative_confidence
    ):
        recommendation = "worker_only"

    return {
        "recommendation": recommendation,
        "prediction_count": total,
        "label_counts": label_counts,
        "label_max_confidence": label_max_confidence,
        "carried_panel_count": carried_count,
        "worker_only_count": worker_count,
        "carried_panel_ratio": round(carried_ratio, 6),
        "worker_only_ratio": round(worker_ratio, 6),
        "carried_panel_max_confidence": round(carried_confidence, 6),
        "worker_only_max_confidence": round(worker_confidence, 6),
        "predictions": predictions,
    }


def classifier_features(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "person_panel_crop_recommendation": str(summary.get("recommendation") or ""),
        "person_panel_crop_positive_crops": int(summary.get("carried_panel_count") or 0),
        "person_panel_crop_negative_crops": int(summary.get("worker_only_count") or 0),
        "person_panel_crop_total_crops": int(summary.get("prediction_count") or 0),
        "person_panel_crop_positive_ratio": float(summary.get("carried_panel_ratio") or 0.0),
        "person_panel_crop_max_confidence": float(summary.get("carried_panel_max_confidence") or 0.0),
        "person_panel_crop_summary": summary if summary else None,
    }


@lru_cache(maxsize=4)
def _load_model(model_path: str) -> Any | None:
    try:
        from ultralytics import YOLO
    except ImportError:
        return None
    return YOLO(model_path)


@lru_cache(maxsize=512)
def _classify_crop_paths_cached(model_path: str, crop_paths: tuple[str, ...]) -> dict[str, Any]:
    path = Path(model_path)
    if not path.exists():
        return {
            "model_path": model_path,
            "model_available": False,
            "missing_model_path": model_path,
            **summarize_predictions([]),
        }

    model = _load_model(model_path)
    if model is None:
        return {
            "model_path": model_path,
            "model_available": False,
            "import_error": "ultralytics_unavailable",
            **summarize_predictions([]),
        }

    existing_paths = [Path(item) for item in crop_paths if Path(item).exists()]
    missing_paths = [item for item in crop_paths if not Path(item).exists()]
    if not existing_paths:
        return {
            "model_path": model_path,
            "model_available": True,
            "missing_crop_paths": missing_paths,
            **summarize_predictions([]),
        }

    try:
        results = model.predict(source=[str(item) for item in existing_paths], imgsz=224, verbose=False)
    except Exception:
        return {
            "model_path": model_path,
            "model_available": True,
            "missing_crop_paths": missing_paths,
            "prediction_error": "crop_decode_failed",
            **summarize_predictions([]),
        }
    predictions: list[dict[str, Any]] = []
    for crop_path, result in zip(existing_paths, results):
        probs = getattr(result, "probs", None)
        if probs is None:
            continue
        top1 = int(probs.top1)
        names = getattr(result, "names", {}) or {}
        label = str(names.get(top1, top1))
        predictions.append(
            {
                "crop_path": str(crop_path),
                "label": label,
                "confidence": round(float(probs.top1conf), 6),
            }
        )

    return {
        "model_path": model_path,
        "model_available": True,
        "missing_crop_paths": missing_paths,
        **summarize_predictions(predictions),
    }


def summarize_crop_paths(crop_paths: list[str] | tuple[str, ...], *, model_path: str | Path | None = None) -> dict[str, Any]:
    selected_model_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    normalized = tuple(str(Path(item)) for item in as_list(crop_paths) if str(item).strip())
    return _classify_crop_paths_cached(str(selected_model_path), normalized)


def crop_with_padding(image: Any, box_xywh: Any, *, padding: float = 0.20) -> Any | None:
    try:
        x, y, width, height = [float(value) for value in box_xywh]
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    image_height, image_width = image.shape[:2]
    pad_x = width * padding
    pad_y = height * padding
    left = max(int(round(x - pad_x)), 0)
    top = max(int(round(y - pad_y)), 0)
    right = min(int(round(x + width + pad_x)), image_width)
    bottom = min(int(round(y + height + pad_y)), image_height)
    if right <= left or bottom <= top:
        return None
    return image[top:bottom, left:right]


def summarize_panel_box_crop(
    image: Any,
    panel_box_xywh: Any,
    *,
    model_path: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    crop = crop_with_padding(image, panel_box_xywh)
    if crop is None:
        return summarize_predictions([])

    selected_model_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    if not selected_model_path.exists():
        return {
            "model_path": str(selected_model_path),
            "model_available": False,
            "missing_model_path": str(selected_model_path),
            **summarize_predictions([]),
        }

    model = _load_model(str(selected_model_path))
    if model is None:
        return {
            "model_path": str(selected_model_path),
            "model_available": False,
            "import_error": "ultralytics_unavailable",
            **summarize_predictions([]),
        }

    try:
        results = model.predict(source=[crop], imgsz=224, verbose=False)
    except Exception:
        return {
            "model_path": str(selected_model_path),
            "model_available": True,
            "prediction_error": "crop_predict_failed",
            **summarize_predictions([]),
        }
    predictions: list[dict[str, Any]] = []
    for result in results:
        probs = getattr(result, "probs", None)
        if probs is None:
            continue
        top1 = int(probs.top1)
        names = getattr(result, "names", {}) or {}
        label = str(names.get(top1, top1))
        predictions.append(
            {
                "label": label,
                "confidence": round(float(probs.top1conf), 6),
            }
        )

    return {
        "model_path": str(selected_model_path),
        "model_available": True,
        **summarize_predictions(predictions),
    }
