from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.freeze_factory2_diagnostics import freeze_diagnostics


def _write_source_diagnostic(tmp_path: Path, name: str) -> Path:
    diagnostic_dir = tmp_path / "data" / "diagnostics" / "event-windows" / name
    receipts_dir = diagnostic_dir / "track_receipts"
    crops_dir = receipts_dir / "track-000001-crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    (diagnostic_dir / "overlay_sheet.jpg").write_bytes(b"sheet")
    (diagnostic_dir / "overlay_video.mp4").write_bytes(b"video")
    (diagnostic_dir / "hard_negative_manifest.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "image_path": str(crops_dir / "crop-01-source.jpg"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (crops_dir / "crop-01-source.jpg").write_bytes(b"crop")
    (receipts_dir / "track-000001-sheet.jpg").write_bytes(b"card")

    receipt_path = receipts_dir / "track-000001.json"
    receipt_path.write_text(
        json.dumps(
            {
                "review_assets": {
                    "overlay_sheet_path": str(diagnostic_dir / "overlay_sheet.jpg"),
                    "overlay_video_path": str(diagnostic_dir / "overlay_video.mp4"),
                    "track_sheet_path": str(receipts_dir / "track-000001-sheet.jpg"),
                    "raw_crop_paths": [str(crops_dir / "crop-01-source.jpg")],
                }
            }
        ),
        encoding="utf-8",
    )
    diagnostic_path = diagnostic_dir / "diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "overlay_sheet_path": str(diagnostic_dir / "overlay_sheet.jpg"),
                "overlay_video_path": str(diagnostic_dir / "overlay_video.mp4"),
                "hard_negative_manifest_path": str(diagnostic_dir / "hard_negative_manifest.json"),
                "track_receipts": [str(receipt_path)],
                "track_receipt_cards": [str(receipts_dir / "track-000001-sheet.jpg")],
            }
        ),
        encoding="utf-8",
    )
    return diagnostic_path


def test_freeze_diagnostics_copies_directory_and_rewrites_internal_paths(tmp_path: Path) -> None:
    source_diagnostic = _write_source_diagnostic(tmp_path, "factory2-review-0014-000-030s-panel-v1-5fps")
    output_root = tmp_path / "data" / "diagnostics" / "frozen" / "factory2-narrow-v1"

    manifest = freeze_diagnostics(
        diagnostic_paths=[source_diagnostic],
        output_root=output_root,
        force=False,
    )

    assert manifest["schema_version"] == "factory-frozen-diagnostics-v1"
    frozen_path = Path(manifest["diagnostics"][0]["frozen_diagnostic_path"])
    assert frozen_path == output_root / "factory2-review-0014-000-030s-panel-v1-5fps" / "diagnostic.json"
    assert frozen_path.exists()
    assert frozen_path.read_text(encoding="utf-8") != source_diagnostic.read_text(encoding="utf-8")

    frozen_payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    frozen_receipt_path = Path(frozen_payload["track_receipts"][0])
    frozen_receipt_payload = json.loads(frozen_receipt_path.read_text(encoding="utf-8"))

    assert str(output_root) in frozen_payload["overlay_sheet_path"]
    assert str(output_root) in frozen_payload["overlay_video_path"]
    assert str(output_root) in frozen_payload["hard_negative_manifest_path"]
    assert str(output_root) in frozen_payload["track_receipts"][0]
    assert str(output_root) in frozen_payload["track_receipt_cards"][0]
    assert str(output_root) in frozen_receipt_payload["review_assets"]["overlay_sheet_path"]
    assert str(output_root) in frozen_receipt_payload["review_assets"]["track_sheet_path"]
    assert str(output_root) in frozen_receipt_payload["review_assets"]["raw_crop_paths"][0]


def test_freeze_diagnostics_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    source_diagnostic = _write_source_diagnostic(tmp_path, "factory2-review-0014-000-030s-panel-v1-5fps")
    output_root = tmp_path / "data" / "diagnostics" / "frozen" / "factory2-narrow-v1"
    freeze_diagnostics(diagnostic_paths=[source_diagnostic], output_root=output_root, force=False)

    with pytest.raises(FileExistsError):
        freeze_diagnostics(diagnostic_paths=[source_diagnostic], output_root=output_root, force=False)

