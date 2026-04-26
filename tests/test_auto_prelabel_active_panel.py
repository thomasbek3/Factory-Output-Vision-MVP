import json
from pathlib import Path

import pytest

from scripts import auto_prelabel_active_panel as prelabel


def test_parse_args_uses_requested_defaults():
    args = prelabel.parse_args([])

    assert args.manifest == Path("data/videos/selected_frames/autopilot-v1/manifest.json")
    assert args.output == Path("data/labels/active_panel_candidates.json")
    assert args.model == []
    assert args.confidence == 0.25
    assert args.limit is None
    assert args.force is False


def test_choose_model_paths_prioritizes_existing_defaults(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    caleb = models_dir / "caleb_metal_panel.pt"
    panel = models_dir / "panel_in_transit.pt"
    caleb.write_text("weights", encoding="utf-8")
    panel.write_text("weights", encoding="utf-8")

    assert prelabel.choose_model_paths([], repo_root=tmp_path) == [panel, caleb]
    assert prelabel.choose_model_paths([Path("custom.pt")], repo_root=tmp_path) == [
        Path("custom.pt")
    ]


def test_load_selected_frames_manifest_validates_rows_and_applies_limit(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "frame_path": "frames/a.jpg",
                    "video_path": "video.mp4",
                    "timestamp": 1.25,
                    "width": 640,
                    "height": 480,
                },
                {
                    "frame_path": "frames/b.jpg",
                    "video_path": "video.mp4",
                    "timestamp_seconds": 2.5,
                    "width": 800,
                    "height": 600,
                },
            ]
        ),
        encoding="utf-8",
    )

    rows = prelabel.load_selected_frames_manifest(manifest_path, limit=1)

    assert rows == [
        {
            "frame_path": "frames/a.jpg",
            "video_path": "video.mp4",
            "timestamp_seconds": 1.25,
            "width": 640,
            "height": 480,
        }
    ]


def test_load_selected_frames_manifest_rejects_invalid_shape(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"labels": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="list"):
        prelabel.load_selected_frames_manifest(manifest_path)


def test_normalize_box_xyxy_clips_and_rejects_degenerate_boxes():
    assert prelabel.normalize_box_xyxy([-10.2, 5, 640.8, 999], width=640, height=480) == [
        0,
        5,
        640,
        480,
    ]

    with pytest.raises(ValueError, match="degenerate"):
        prelabel.normalize_box_xyxy([9, 10, 9, 12], width=640, height=480)


def test_build_candidate_label_matches_review_manifest_contract():
    frame = {
        "frame_path": "data/videos/selected_frames/line 1_t000001.25.jpg",
        "video_path": "data/videos/line 1.mp4",
        "timestamp_seconds": 1.25,
        "width": 640,
        "height": 480,
    }

    label = prelabel.build_candidate_label(
        frame,
        {
            "box": [-5, 10, 300.6, 240],
            "confidence": 0.87,
            "class_index": 2,
            "class_name": "panel",
        },
        model_path=Path("models/panel_in_transit.pt"),
        detection_index=0,
    )

    assert label == {
        "label_id": "data-videos-selected_frames-line-1_t000001.25-active_panel-000",
        "frame_id": "line-1_t000001.25",
        "image_width": 640,
        "image_height": 480,
        "class_name": "active_panel",
        "box": [0, 10, 300.6, 240],
        "confidence": 0.87,
        "source_type": "box",
        "metadata": {
            "model_path": "models/panel_in_transit.pt",
            "model_class_name": "panel",
            "model_class_index": 2,
            "frame_path": "data/videos/selected_frames/line 1_t000001.25.jpg",
            "video_path": "data/videos/line 1.mp4",
            "timestamp_seconds": 1.25,
        },
    }


def test_write_candidate_manifest_refuses_overwrite_without_force(tmp_path):
    output_path = tmp_path / "candidates.json"
    output_path.write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError, match="overwrite"):
        prelabel.write_candidate_manifest([], output_path=output_path, force=False)


def test_run_prelabel_writes_candidates_with_fake_detector_without_ultralytics(tmp_path):
    frame_path = tmp_path / "frames" / "a.jpg"
    frame_path.parent.mkdir()
    frame_path.write_text("not a real image", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "frame_path": str(frame_path),
                    "video_path": "video.mp4",
                    "timestamp": 3.0,
                    "width": 100,
                    "height": 80,
                }
            ]
        ),
        encoding="utf-8",
    )
    model_path = tmp_path / "panel.pt"
    output_path = tmp_path / "labels" / "candidates.json"
    calls = []

    def fake_detector(*, frame_path, model_path, confidence):
        calls.append((frame_path, model_path, confidence))
        return [
            {
                "box": [1, 2, 20, 30],
                "confidence": 0.91,
                "class_index": 0,
                "class_name": "active_panel",
            }
        ]

    result = prelabel.run_prelabel(
        manifest_path=manifest_path,
        output_path=output_path,
        model_paths=[model_path],
        confidence=0.5,
        limit=None,
        force=False,
        detector_runner=fake_detector,
    )

    assert calls == [(frame_path, model_path, 0.5)]
    assert result["schema_version"] == "active-panel-candidates-v1"
    assert result["labels"][0]["confidence"] == 0.91
    assert json.loads(output_path.read_text(encoding="utf-8")) == result



def test_run_prelabel_rejects_empty_model_list_before_writing(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("[]", encoding="utf-8")
    output_path = tmp_path / "candidates.json"

    with pytest.raises(ValueError, match="No model paths"):
        prelabel.run_prelabel(
            manifest_path=manifest_path,
            output_path=output_path,
            model_paths=[],
            confidence=0.5,
            limit=None,
            force=False,
            detector_runner=lambda **kwargs: [],
        )

    assert not output_path.exists()


def test_run_prelabel_resolves_relative_frame_paths_against_manifest_parent(tmp_path):
    manifest_dir = tmp_path / "selected"
    frame_path = manifest_dir / "frame.jpg"
    frame_path.parent.mkdir(parents=True)
    frame_path.write_text("not a real image", encoding="utf-8")
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "frame_path": "frame.jpg",
                    "video_path": "video.mp4",
                    "timestamp": 1.0,
                    "width": 100,
                    "height": 80,
                }
            ]
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_detector(*, frame_path, model_path, confidence):
        calls.append(frame_path)
        return []

    prelabel.run_prelabel(
        manifest_path=manifest_path,
        output_path=tmp_path / "candidates.json",
        model_paths=[tmp_path / "model.pt"],
        confidence=0.5,
        limit=None,
        force=False,
        detector_runner=fake_detector,
    )

    assert calls == [frame_path]
