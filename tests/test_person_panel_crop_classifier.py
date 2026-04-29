from __future__ import annotations

import numpy as np

from app.services.person_panel_crop_classifier import classifier_features, summarize_predictions


def test_summarize_predictions_marks_strong_carried_panel_bundle() -> None:
    summary = summarize_predictions(
        [
            {"crop_path": "a.jpg", "label": "carried_panel", "confidence": 0.998},
            {"crop_path": "b.jpg", "label": "carried_panel", "confidence": 0.991},
        ]
    )

    assert summary["recommendation"] == "carried_panel"
    assert summary["carried_panel_count"] == 2
    assert summary["worker_only_count"] == 0
    assert summary["carried_panel_ratio"] == 1.0


def test_summarize_predictions_marks_worker_only_bundle() -> None:
    summary = summarize_predictions(
        [
            {"crop_path": "a.jpg", "label": "worker_only", "confidence": 0.998},
            {"crop_path": "b.jpg", "label": "worker_only", "confidence": 0.997},
        ]
    )

    assert summary["recommendation"] == "worker_only"
    assert summary["worker_only_ratio"] == 1.0


def test_classifier_features_projects_summary_into_gate_fields() -> None:
    features = classifier_features(
        {
            "recommendation": "carried_panel",
            "prediction_count": 4,
            "carried_panel_count": 3,
            "worker_only_count": 1,
            "carried_panel_ratio": 0.75,
            "carried_panel_max_confidence": 0.999,
        }
    )

    assert features["person_panel_crop_recommendation"] == "carried_panel"
    assert features["person_panel_crop_positive_crops"] == 3
    assert features["person_panel_crop_total_crops"] == 4


def test_crop_with_padding_extracts_context_window() -> None:
    from app.services.person_panel_crop_classifier import crop_with_padding

    image = np.arange(100 * 100 * 3, dtype=np.uint8).reshape(100, 100, 3)
    crop = crop_with_padding(image, (40, 40, 10, 10), padding=0.20)

    assert crop is not None
    assert crop.shape[0] == 14
    assert crop.shape[1] == 14
