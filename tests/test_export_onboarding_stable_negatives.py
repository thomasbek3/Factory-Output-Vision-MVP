from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.export_hard_negatives import load_hard_negative_manifest
from scripts.export_onboarding_stable_negatives import build_stable_negative_manifest, main


def _proposals_file(tmp_path: Path) -> Path:
    path = tmp_path / "proposals.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "factory-vision-onboarding-event-proposals-v1",
                "station_id": "line-a",
                "proposals": [
                    {
                        "candidate_id": "seg-0-motion-1",
                        "candidate_type": "event_candidate",
                        "segment_id": "seg-0",
                        "segment_path": str(tmp_path / "segment.mkv"),
                        "center_offset_sec": 10.0,
                        "end_offset_sec": 14.0,
                    },
                    {
                        "candidate_id": "seg-0-stable-1",
                        "candidate_type": "hard_negative_candidate",
                        "segment_id": "seg-0",
                        "segment_path": str(tmp_path / "segment.mkv"),
                        "center_offset_sec": 30.0,
                        "end_offset_sec": 34.0,
                        "motion_summary": {"peak_motion_score": 0.0},
                    },
                    {
                        "candidate_id": "seg-0-stable-2",
                        "candidate_type": "hard_negative_candidate",
                        "segment_id": "seg-0",
                        "segment_path": str(tmp_path / "segment.mkv"),
                        "center_offset_sec": 50.0,
                        "end_offset_sec": 54.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _frame_provider(fail_at: float | None = None):
    def _read(video_path: Path, timestamp_sec: float) -> np.ndarray:
        if fail_at is not None and timestamp_sec == fail_at:
            raise RuntimeError("unreadable frame")
        return np.full((120, 160, 3), 60, dtype=np.uint8)

    return _read


def test_manifest_built_from_stable_negatives_only(tmp_path: Path) -> None:
    proposals = _proposals_file(tmp_path)
    manifest_path = build_stable_negative_manifest(
        event_proposals_path=proposals,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(),
    )
    manifest = load_hard_negative_manifest(manifest_path)
    assert len(manifest["items"]) == 2  # event candidate excluded
    item = manifest["items"][0]
    assert item["label"] == "hard_negative"
    assert item["reason"] == "stable_low_motion_window"
    assert all(Path(p).exists() for p in item["assets"]["raw_crop_paths"])


def test_unreadable_negative_is_skipped(tmp_path: Path) -> None:
    proposals = _proposals_file(tmp_path)
    manifest_path = build_stable_negative_manifest(
        event_proposals_path=proposals,
        work_dir=tmp_path / "work",
        frame_provider=_frame_provider(fail_at=30.0),
    )
    manifest = load_hard_negative_manifest(manifest_path)
    assert len(manifest["items"]) == 1


def test_cli_end_to_end_produces_yolo_export(tmp_path: Path, capsys, monkeypatch) -> None:
    proposals = _proposals_file(tmp_path)
    import scripts.export_onboarding_stable_negatives as module

    monkeypatch.setattr(module, "_default_frame_provider", lambda: _frame_provider())
    exit_code = main(
        [
            "--event-proposals",
            str(proposals),
            "--work-dir",
            str(tmp_path / "work"),
            "--out-dir",
            str(tmp_path / "export"),
            "--force",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    summary = json.loads(captured.out)
    assert summary["negative_count"] == 2
    export = json.loads(Path(summary["hard_negative_export"]).read_text(encoding="utf-8"))
    assert export["schema_version"] == "factory-hard-negative-export-v1"
    for item in export["items"]:
        assert item["exported_image_path"] and Path(item["exported_image_path"]).exists()
        label_path = Path(item["exported_label_path"])
        assert label_path.exists() and label_path.read_text(encoding="utf-8") == ""
        assert item["review_only"] is False
