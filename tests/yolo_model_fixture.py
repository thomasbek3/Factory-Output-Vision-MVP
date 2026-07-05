from __future__ import annotations

from pathlib import Path


OFFLOADED_PANEL_MODEL = Path(
    "/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/panel_in_transit.pt"
)


def receipt_validation_model_path() -> Path | None:
    """Return a real YOLO weight for receipt path-matching tests."""
    auto_model = Path("yolov8n.pt").resolve()
    if auto_model.exists():
        return auto_model

    try:
        from ultralytics import YOLO

        YOLO("yolov8n.pt")
    except Exception:
        pass

    if auto_model.exists():
        return auto_model
    if OFFLOADED_PANEL_MODEL.exists():
        return OFFLOADED_PANEL_MODEL.resolve()
    return None
