import numpy as np

from scripts.analyze_panel_crop_evidence import (
    analyze_crop_array,
    analyze_receipt,
    analyze_work_queue_report,
)


def mesh_like_image(size=96, spacing=8):
    image = np.full((size, size, 3), 230, dtype=np.uint8)
    image[:, ::spacing, :] = 20
    image[::spacing, :, :] = 20
    return image


def solid_worker_like_image(size=96):
    image = np.full((size, size, 3), 120, dtype=np.uint8)
    image[16:80, 24:72, :] = 90
    return image


def test_panel_crop_evidence_scores_wire_mesh_above_solid_worker_crop():
    mesh = analyze_crop_array(mesh_like_image())
    worker = analyze_crop_array(solid_worker_like_image())

    assert mesh["decision"] == "panel_texture_candidate"
    assert worker["decision"] == "low_panel_texture"
    assert mesh["panel_texture_score"] > worker["panel_texture_score"]
    assert mesh["edge_density"] > worker["edge_density"]


def test_analyze_receipt_carries_crop_evidence_and_recommendation(tmp_path):
    receipt_path = tmp_path / "track-000007.json"
    crop_path = "crops/crop-01-source.jpg"
    receipt_path.write_text(
        '{"track_id": 7, "review_assets": {"raw_crop_paths": ["%s"]}, "perception_gate": {"decision": "uncertain", "reason": "source_without_output_settle"}}'
        % crop_path,
        encoding="utf-8",
    )

    def loader(path):
        assert path == crop_path
        return mesh_like_image()

    result = analyze_receipt(receipt_path, image_loader=loader)

    assert result["track_id"] == 7
    assert result["crop_count"] == 1
    assert result["panel_texture_candidate_crops"] == 1
    assert result["recommendation"] == "inspect_as_possible_panel_texture"
    assert result["crop_evidence"][0]["decision"] == "panel_texture_candidate"


def test_analyze_work_queue_report_limits_to_top_items(tmp_path):
    first = tmp_path / "track-000001.json"
    second = tmp_path / "track-000002.json"
    for path in [first, second]:
        path.write_text(
            '{"track_id": 1, "review_assets": {"raw_crop_paths": ["crop.jpg"]}}',
            encoding="utf-8",
        )
    proof_report = {
        "source_token_work_queue": {
            "top_items": [
                {"track_id": 1, "receipt_json_path": str(first)},
                {"track_id": 2, "receipt_json_path": str(second)},
            ]
        }
    }

    result = analyze_work_queue_report(proof_report, limit=1, image_loader=lambda path: solid_worker_like_image())

    assert result["schema_version"] == "factory-panel-crop-evidence-v1"
    assert result["receipt_count"] == 1
    assert result["summary"]["low_panel_texture_receipts"] == 1
    assert result["receipts"][0]["track_id"] == 1
