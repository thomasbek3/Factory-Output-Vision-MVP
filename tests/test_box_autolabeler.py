from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.box_autolabeler import (
    assign_event_splits,
    propose_auto_boxes,
    write_auto_box_manifest,
)
from scripts import propose_auto_boxes as propose_auto_boxes_cli
from scripts.research.factory2.assemble_active_panel_dataset import assemble_dataset
from scripts.research.factory2.review_labels_ai import review_manifest

WIDTH, HEIGHT = 320, 240
BOX = (80, 60, 180, 140)  # x1, y1, x2, y2 of the synthetic placed part


def _background() -> np.ndarray:
    frame = np.full((HEIGHT, WIDTH, 3), 40, dtype=np.uint8)
    return frame


def _with_part(frame: np.ndarray, *, jitter: int = 0) -> np.ndarray:
    out = frame.copy()
    x1, y1, x2, y2 = BOX
    out[y1 + jitter : y2 + jitter, x1 + jitter : x2 + jitter] = (200, 200, 200)
    return out


def _placing(frame: np.ndarray) -> np.ndarray:
    """Placement act: the part is arriving and a 'hand' partially covers the landing region."""
    out = _with_part(frame)
    x1, y1, x2, y2 = BOX
    out[y1 : y1 + 40, x1 : x1 + 50] = (90, 120, 90)
    return out


def _frame_provider(
    overrides: dict[float, np.ndarray] | None = None,
    *,
    before: np.ndarray | None = None,
    after: np.ndarray | None = None,
    during: np.ndarray | None = None,
):
    """Timeline for the fixture window (before_sec=2, center=6, after_sec=10):
    <=2.0 before-state, (2.0, 8.6) placement act, >=8.6 settled after-state."""
    before_frame = before if before is not None else _background()
    after_frame = after if after is not None else _with_part(_background())
    during_frame = during if during is not None else _placing(_background())

    def _read(video_path: Path, timestamp_sec: float) -> np.ndarray:
        if overrides is not None and timestamp_sec in overrides:
            return overrides[timestamp_sec]
        if timestamp_sec <= 2.0:
            return before_frame
        if timestamp_sec < 8.6:
            return during_frame
        return after_frame

    return _read


def _fixtures(tmp_path: Path, packet_ids: list[str]) -> tuple[Path, Path]:
    packet_rows = []
    for packet_id in packet_ids:
        packet_path = tmp_path / f"{packet_id}.json"
        packet_path.write_text(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "window_id": f"{packet_id}-window",
                    "station_id": "line-a",
                    "segment_id": "chunk_000",
                    "segment_path": str(tmp_path / "segment.mkv"),
                    "window": {
                        "start_offset_sec": 2.0,
                        "center_offset_sec": 6.0,
                        "end_offset_sec": 10.0,
                        "before_sec": 2.0,
                        "after_sec": 10.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        packet_rows.append({"packet_id": packet_id, "packet_manifest_path": str(packet_path)})
    packet_manifest = tmp_path / "evidence_manifest.json"
    packet_manifest.write_text(json.dumps({"packets": packet_rows, "station_id": "line-a"}), encoding="utf-8")

    silver = tmp_path / "silver.json"
    silver.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-silver-training-candidates-v1",
                "items": [
                    {"item_id": f"{packet_id}-silver", "packet_id": packet_id, "training_eligible": True}
                    for packet_id in packet_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    return silver, packet_manifest


def test_diff_box_labels_placement_act_frames(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(),
    )
    labels = payload["labels"]
    assert len(labels) == 3  # top placement-act frames, capped by frames_per_event
    # the landing box is recovered then expanded by BOX_EXPAND_RATIO (15%)
    x1, y1, x2, y2 = labels[0]["box"]
    assert BOX[0] - 22 <= x1 <= BOX[0] and BOX[1] - 18 <= y1 <= BOX[1]
    assert BOX[2] <= x2 <= BOX[2] + 22 and BOX[3] <= y2 <= BOX[3] + 18
    # only frames during the act are labeled, never the settled tail
    for label in labels:
        assert 2.0 < label["metadata"]["timestamp_seconds"] < 8.6
        assert label["metadata"]["label_semantic"] == "part_during_placement"
    assert labels[0]["confidence"] is None
    assert labels[0]["class_name"] == "active_panel"
    assert labels[0]["metadata"]["label_authority_tier"] == "bronze"
    assert Path(labels[0]["metadata"]["frame_path"]).exists()
    assert payload["summary"]["events_with_box"] == 1


def test_no_visible_change_is_skipped(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(before=_background(), after=_background()),
    )
    assert payload["labels"] == []
    assert payload["summary"]["skipped"][0]["reason"] in {"no_visible_change", "box_too_small"}


def test_global_motion_guard(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    rng = np.random.default_rng(7)
    noisy = rng.integers(0, 255, size=(HEIGHT, WIDTH, 3), dtype=np.uint8)
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(before=_background(), after=noisy),
    )
    assert payload["labels"] == []
    assert payload["summary"]["skipped"][0]["reason"] == "global_motion"


def test_oversized_box_rejected(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    huge = _background()
    huge[10 : HEIGHT - 10, 10 : WIDTH - 10] = (220, 220, 220)
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(before=_background(), after=huge),
    )
    assert payload["labels"] == []
    assert payload["summary"]["skipped"][0]["reason"] in {"box_too_large", "global_motion"}


def test_settled_frames_are_never_labeled(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    # the part appears instantly and never has a placement act: every act-window frame
    # matches the settled after-state, so labeling it would poison training
    provider = _frame_provider(during=_with_part(_background()))
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=provider,
    )
    assert payload["labels"] == []
    assert payload["summary"]["skipped"][0]["reason"] == "no_transition_frames"


def test_event_granular_split_is_deterministic() -> None:
    packet_ids = [f"packet-{index}" for index in range(10)]
    first = assign_event_splits(packet_ids, val_fraction=0.2)
    second = assign_event_splits(list(reversed(packet_ids)), val_fraction=0.2)
    assert first == second
    assert sum(1 for split in first.values() if split == "val") == 2
    single = assign_event_splits(["only-one"], val_fraction=0.2)
    assert single == {"only-one": "train"}


def test_round_trip_through_review_and_assembler(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one", "packet-two", "packet-three"])
    payload = propose_auto_boxes(
        silver_dataset_path=silver,
        packet_manifest_path=packets,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(),
        val_fraction=0.34,
    )
    assert payload["summary"]["label_count"] > 0

    reviewed = review_manifest(payload)
    assert reviewed["schema_version"] == "label-quality-reviewed-v1"
    assert len(reviewed["trainable_labels"]) == payload["summary"]["label_count"]
    assert not reviewed["rejected"]

    reviewed_path = tmp_path / "reviewed.json"
    reviewed_path.write_text(json.dumps(reviewed, indent=2), encoding="utf-8")
    dataset_manifest_path = assemble_dataset(
        out_dir=tmp_path / "dataset",
        reviewed_label_manifest=reviewed_path,
        hard_negative_export=None,
    )
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    assert dataset_manifest["schema_version"] == "active-panel-yolo-dataset-v1"
    items = dataset_manifest["items"]
    assert dataset_manifest["summary"]["positive_count"] == payload["summary"]["label_count"]
    splits = {item["split"] for item in items}
    assert splits == {"train", "val"}
    sample = next(item for item in items if item["kind"] == "positive")
    label_line = Path(sample["label_path"]).read_text(encoding="utf-8").strip()
    parts = label_line.split()
    assert parts[0] == "0" and len(parts) == 5
    assert all(0.0 < float(value) <= 1.0 for value in parts[1:])


def test_yolo_world_refuses_without_model_or_download(tmp_path: Path) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    with pytest.raises(ValueError, match="yolo_world backend needs"):
        propose_auto_boxes(
            silver_dataset_path=silver,
            packet_manifest_path=packets,
            work_dir=tmp_path / "work",
            backend="yolo_world",
            frame_provider=_frame_provider(),
        )


def test_write_manifest_respects_force(tmp_path: Path) -> None:
    output = tmp_path / "boxes.json"
    write_auto_box_manifest(output, {"a": 1})
    with pytest.raises(FileExistsError):
        write_auto_box_manifest(output, {"a": 1})
    write_auto_box_manifest(output, {"a": 2}, force=True)


def test_cli_smoke_reports_summary(tmp_path: Path, capsys, monkeypatch) -> None:
    silver, packets = _fixtures(tmp_path, ["packet-one"])
    # The CLI has no frame-provider injection; patch the default provider for the smoke test.
    import app.services.box_autolabeler as box_autolabeler

    monkeypatch.setattr(box_autolabeler, "_default_frame_provider", lambda: _frame_provider())
    output = tmp_path / "boxes.json"
    exit_code = propose_auto_boxes_cli.main(
        [
            "--silver-dataset",
            str(silver),
            "--packet-manifest",
            str(packets),
            "--work-dir",
            str(tmp_path / "work"),
            "--output",
            str(output),
            "--force",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    summary = json.loads(captured.out)
    assert summary["label_count"] == 3
    assert output.exists()
