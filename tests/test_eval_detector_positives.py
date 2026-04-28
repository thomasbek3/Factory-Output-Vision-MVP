import json
from pathlib import Path

import pytest

from scripts import eval_detector_positives as pos_eval


def _write_dataset(tmp_path: Path) -> Path:
    out_dir = tmp_path / "dataset"
    (out_dir / "images" / "train").mkdir(parents=True)
    (out_dir / "labels" / "train").mkdir(parents=True)
    pos_image = out_dir / "images" / "train" / "pos-panel.jpg"
    neg_image = out_dir / "images" / "train" / "neg-worker.jpg"
    pos_label = out_dir / "labels" / "train" / "pos-panel.txt"
    neg_label = out_dir / "labels" / "train" / "neg-worker.txt"
    pos_image.write_text("positive", encoding="utf-8")
    neg_image.write_text("negative", encoding="utf-8")
    pos_label.write_text("0 0.5 0.5 0.4 0.2\n", encoding="utf-8")
    neg_label.write_text("", encoding="utf-8")
    data_yaml = out_dir / "data.yaml"
    data_yaml.write_text("path: .\ntrain: images/train\nval: images/val\nnames:\n  0: active_panel\n", encoding="utf-8")
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "active-panel-yolo-dataset-v1",
                "items": [
                    {
                        "kind": "positive",
                        "label_id": "pos-panel-label",
                        "class_name": "active_panel",
                        "image_path": str(pos_image),
                        "label_path": str(pos_label),
                        "split": "train",
                    },
                    {
                        "kind": "hard_negative",
                        "negative_id": "neg-worker",
                        "image_path": str(neg_image),
                        "label_path": str(neg_label),
                        "split": "train",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return data_yaml


def test_loads_positives_from_dataset_manifest_next_to_data_yaml(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)

    rows = pos_eval.load_positive_items(data_yaml=data_yaml, dataset_manifest=None)

    assert len(rows) == 1
    assert rows[0]["positive_id"] == "pos-panel-label"
    assert rows[0]["class_name"] == "active_panel"


def test_scans_non_empty_labels_when_manifest_is_missing(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    (data_yaml.parent / "dataset_manifest.json").unlink()

    rows = pos_eval.load_positive_items(data_yaml=data_yaml, dataset_manifest=None)

    assert len(rows) == 1
    assert rows[0]["positive_id"] == "pos-panel"
    assert Path(rows[0]["image_path"]).name == "pos-panel.jpg"


def test_parse_yolo_labels_to_pixel_boxes(tmp_path: Path) -> None:
    label_path = tmp_path / "label.txt"
    label_path.write_text("0 0.5 0.5 0.4 0.2\nbad line\n0 nan 0.5 0.1 0.1\n", encoding="utf-8")

    boxes = pos_eval.parse_yolo_label_boxes(label_path, image_width=100, image_height=50)

    assert boxes == [{"label_index": 0, "line_number": 1, "class_index": 0, "box": [30.0, 20.0, 70.0, 30.0]}]


def test_evaluate_detector_positives_writes_recall_report(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    output = tmp_path / "positive_report.json"

    def fake_detector(*, image_paths: list[Path], model_path: Path, confidence: float):
        assert model_path == Path("models/panel_in_transit.pt")
        assert confidence == 0.25
        return {
            str(image_paths[0]): [
                {"box": [31, 19, 71, 31], "confidence": 0.8, "class_index": 0, "class_name": "active_panel"},
                {"box": [0, 0, 5, 5], "confidence": 0.1, "class_index": 0, "class_name": "active_panel"},
            ]
        }

    report = pos_eval.evaluate_detector_positives(
        data_yaml=data_yaml,
        dataset_manifest=None,
        model_path=Path("models/panel_in_transit.pt"),
        output_path=output,
        confidence=0.25,
        iou_threshold=0.3,
        detector_runner=fake_detector,
        image_size_provider=lambda image_path: (100, 50),
    )

    assert report["schema_version"] == "active-panel-positive-detector-eval-v1"
    assert report["summary"]["positive_images"] == 1
    assert report["summary"]["positive_labels"] == 1
    assert report["summary"]["matched_labels"] == 1
    assert report["summary"]["missed_labels"] == 0
    assert report["summary"]["label_recall"] == 1.0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["items"][0]["matches"][0]["confidence"] == 0.8


def test_evaluate_detector_positives_reports_misses(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    output = tmp_path / "positive_report.json"

    report = pos_eval.evaluate_detector_positives(
        data_yaml=data_yaml,
        dataset_manifest=None,
        model_path=Path("model.pt"),
        output_path=output,
        detector_runner=lambda **kwargs: {},
        image_size_provider=lambda image_path: (100, 50),
    )

    assert report["summary"]["matched_labels"] == 0
    assert report["summary"]["missed_labels"] == 1
    assert report["summary"]["label_recall"] == 0.0


def test_refuses_to_overwrite_existing_report(tmp_path: Path) -> None:
    data_yaml = _write_dataset(tmp_path)
    output = tmp_path / "positive_report.json"
    output.write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        pos_eval.evaluate_detector_positives(
            data_yaml=data_yaml,
            dataset_manifest=None,
            model_path=Path("model.pt"),
            output_path=output,
            detector_runner=lambda **kwargs: {},
            image_size_provider=lambda image_path: (100, 50),
        )
