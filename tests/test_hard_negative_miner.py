from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.hard_negative_miner import mine_hard_negative_frames
from scripts.assemble_active_panel_dataset import load_hard_negative_rows


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    """One 30s segment; an asserted event window at [10, 14] and a refuted window at [20, 24]."""
    packets = {}
    for packet_id, window in (("packet-assert", (10.0, 14.0)), ("packet-refute", (20.0, 24.0))):
        packet_path = tmp_path / f"{packet_id}.json"
        packet_path.write_text(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "segment_id": "seg-0",
                    "segment_path": str(tmp_path / "segment.mkv"),
                    "window": {"start_offset_sec": window[0], "end_offset_sec": window[1]},
                }
            ),
            encoding="utf-8",
        )
        packets[packet_id] = packet_path

    teacher_labels = tmp_path / "teacher_labels.json"
    teacher_labels.write_text(
        json.dumps(
            {
                "labels": [
                    {
                        "packet_id": "packet-assert",
                        "verification_decision": "assert_completed",
                        "source_packet_manifest_path": str(packets["packet-assert"]),
                    },
                    {
                        "packet_id": "packet-refute",
                        "verification_decision": "refute_completed",
                        "source_packet_manifest_path": str(packets["packet-refute"]),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    segment_manifest = tmp_path / "segment_manifest.json"
    segment_manifest.write_text(
        json.dumps(
            {
                "segments": [
                    {"segment_id": "seg-0", "path": str(tmp_path / "segment.mkv"), "duration_sec": 30.0}
                ]
            }
        ),
        encoding="utf-8",
    )
    return teacher_labels, segment_manifest


def _frame_provider():
    def _read(video_path: Path, timestamp_sec: float) -> np.ndarray:
        return np.full((120, 160, 3), 50, dtype=np.uint8)

    return _read


def test_mines_outside_asserted_windows_only(tmp_path: Path) -> None:
    teacher_labels, segment_manifest = _fixtures(tmp_path)
    fired_at: list[float] = []

    def detector(frame) -> int:  # noqa: ANN001
        return 1  # the v1 model fires everywhere it is allowed to look

    payload = mine_hard_negative_frames(
        model_path=tmp_path / "model.pt",
        teacher_labels_path=teacher_labels,
        segment_manifest_path=segment_manifest,
        base_hard_negative_export_path=None,
        work_dir=tmp_path / "mine",
        output_export_path=tmp_path / "export.json",
        sample_fps=1.0,
        exclusion_margin_sec=2.0,
        max_mined_frames=100,
        detector=detector,
        frame_provider=_frame_provider(),
    )
    mined_ts = [item["evidence"]["timestamp_sec"] for item in payload["items"]]
    # the asserted window [10,14] +/- 2s margin is excluded; the refuted window [20,24] is minable
    assert all(not (8.0 <= ts <= 16.0) for ts in mined_ts)
    assert any(20.0 <= ts <= 24.0 for ts in mined_ts)
    assert payload["mining"]["excluded_window_count"] == 1
    assert payload["mining"]["mined_count"] == len(mined_ts)
    for item in payload["items"]:
        assert Path(item["exported_image_path"]).exists()
        assert Path(item["exported_label_path"]).read_text(encoding="utf-8") == ""
    rows = load_hard_negative_rows(tmp_path / "export.json")
    assert len(rows) == len(mined_ts)


def test_no_detections_mines_nothing(tmp_path: Path) -> None:
    teacher_labels, segment_manifest = _fixtures(tmp_path)
    payload = mine_hard_negative_frames(
        model_path=tmp_path / "model.pt",
        teacher_labels_path=teacher_labels,
        segment_manifest_path=segment_manifest,
        base_hard_negative_export_path=None,
        work_dir=tmp_path / "mine",
        output_export_path=tmp_path / "export.json",
        detector=lambda frame: 0,
        frame_provider=_frame_provider(),
    )
    assert payload["mining"]["mined_count"] == 0
    assert payload["count"] == 0


def test_merges_base_export_rows(tmp_path: Path) -> None:
    teacher_labels, segment_manifest = _fixtures(tmp_path)
    base = tmp_path / "base_export.json"
    base.write_text(
        json.dumps(
            {
                "schema_version": "factory-hard-negative-export-v1",
                "source_manifests": ["base_manifest.json"],
                "items": [{"negative_id": "base-1", "label": "hard_negative", "exported_image_path": "/x/base.jpg"}],
            }
        ),
        encoding="utf-8",
    )
    payload = mine_hard_negative_frames(
        model_path=tmp_path / "model.pt",
        teacher_labels_path=teacher_labels,
        segment_manifest_path=segment_manifest,
        base_hard_negative_export_path=base,
        work_dir=tmp_path / "mine",
        output_export_path=tmp_path / "export.json",
        detector=lambda frame: 0,
        frame_provider=_frame_provider(),
    )
    assert payload["count"] == 1
    assert payload["items"][0]["negative_id"] == "base-1"
    assert "base_manifest.json" in payload["source_manifests"]


def test_mined_frames_capped_and_force(tmp_path: Path) -> None:
    teacher_labels, segment_manifest = _fixtures(tmp_path)
    kwargs = dict(
        model_path=tmp_path / "model.pt",
        teacher_labels_path=teacher_labels,
        segment_manifest_path=segment_manifest,
        base_hard_negative_export_path=None,
        work_dir=tmp_path / "mine",
        output_export_path=tmp_path / "export.json",
        sample_fps=4.0,
        max_mined_frames=5,
        detector=lambda frame: 1,
        frame_provider=_frame_provider(),
    )
    payload = mine_hard_negative_frames(**kwargs)
    assert payload["mining"]["mined_count"] == 5
    with pytest.raises(FileExistsError):
        mine_hard_negative_frames(**kwargs)
    mine_hard_negative_frames(**kwargs, force=True)
