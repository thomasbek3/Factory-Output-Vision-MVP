from pathlib import Path

from scripts.build_morning_proof_report import build_report, main, render_markdown, source_token_key


def write_json(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_build_report_separates_accepted_suppressed_uncertain(tmp_path: Path):
    receipt = tmp_path / "diag" / "track_receipts" / "track-000001.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        """
        {
          "review_assets": {
            "track_sheet_path": "diag/track_receipts/track-000001-sheet.jpg",
            "raw_crop_paths": ["diag/track_receipts/track-000001-crops/crop-01.jpg"]
          }
        }
        """,
        encoding="utf-8",
    )
    diagnostic = write_json(
        tmp_path / "diag" / "diagnostic.json",
        """
        {
          "schema_version": "factory-event-diagnostic-v1",
          "video_path": "data/videos/from-pc/factory2.MOV",
          "model_path": "models/panel_in_transit.pt",
          "person_model_path": "yolo11n.pt",
          "start_timestamp": 78.0,
          "end_timestamp": 118.0,
          "fps": 3.0,
          "frame_count": 120,
          "overlay_sheet_path": "diag/overlay_sheet.jpg",
          "overlay_video_path": "diag/overlay_video.mp4",
          "hard_negative_manifest_path": "diag/hard_negative_manifest.json",
          "perception_gate_summary": {
            "allowed_source_token_tracks": [],
            "track_count": 3,
            "decision_counts": {"allow_source_token": 0, "reject": 2, "uncertain": 1},
            "reason_counts": {"worker_body_overlap": 2, "source_without_output_settle": 1}
          },
          "perception_gate": [
            {
              "track_id": 1,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap", "not_enough_object_outside_person"],
              "evidence": {"source_frames": 5, "output_frames": 0, "person_overlap_ratio": 1.0, "outside_person_ratio": 0.0, "max_displacement": 100.0, "flow_coherence": 0.2}
            },
            {
              "track_id": 2,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap"],
              "evidence": {"source_frames": 4, "output_frames": 0, "person_overlap_ratio": 0.95, "outside_person_ratio": 0.05}
            },
            {
              "track_id": 3,
              "decision": "uncertain",
              "reason": "source_without_output_settle",
              "flags": [],
              "evidence": {"source_frames": 8, "output_frames": 0, "person_overlap_ratio": 0.0, "outside_person_ratio": 1.0}
            }
          ],
          "summary": {"has_source_to_output_candidate": true},
          "track_receipts": ["RECEIPT_PATH", "diag/track_receipts/track-000002.json"],
          "track_receipt_cards": ["diag/track_receipts/track-000001-sheet.jpg"]
        }
        """.replace("RECEIPT_PATH", str(receipt)),
    )
    fp_report = write_json(
        tmp_path / "fp.json",
        """
        {
          "confidence": 0.25,
          "model_path": "models/panel_in_transit.pt",
          "hard_negative_images": 16,
          "images_with_false_positives": 0,
          "false_positive_detections": 0,
          "false_positive_image_rate": 0.0
        }
        """,
    )
    positive_report = write_json(
        tmp_path / "positive.json",
        """
        {
          "confidence": 0.25,
          "iou_threshold": 0.3,
          "model_path": "models/panel_in_transit.pt",
          "summary": {"positive_images": 2, "positive_labels": 2, "matched_labels": 1, "missed_labels": 1, "label_recall": 0.5}
        }
        """,
    )
    better_fp_report = write_json(
        tmp_path / "better-fp.json",
        """
        {
          "confidence": 0.10,
          "model_path": "models/caleb_metal_panel.pt",
          "hard_negative_images": 16,
          "images_with_false_positives": 0,
          "false_positive_detections": 0,
          "false_positive_image_rate": 0.0
        }
        """,
    )
    better_positive_report = write_json(
        tmp_path / "better-positive.json",
        """
        {
          "confidence": 0.10,
          "iou_threshold": 0.3,
          "model_path": "models/caleb_metal_panel.pt",
          "summary": {"positive_images": 2, "positive_labels": 2, "matched_labels": 2, "missed_labels": 0, "label_recall": 1.0}
        }
        """,
    )

    report = build_report(
        diagnostic_paths=[diagnostic],
        fp_report_paths=[fp_report, better_fp_report],
        positive_report_paths=[positive_report, better_positive_report],
    )

    assert report["verdict"] == "auditable_abstention_no_trusted_positive"
    assert report["accepted_count"] == 0
    assert report["suppressed_count"] == 2
    assert report["uncertain_count"] == 1
    assert report["bottleneck"] == "perception_gate_worker_body_overlap"
    assert report["detector_false_positive_eval"]["false_positive_detections"] == 0
    assert report["detector_positive_eval"]["positive_labels"] == 4
    assert report["detector_positive_eval"]["matched_labels"] == 3
    assert report["detector_positive_eval"]["label_recall"] == 0.75
    assert report["detector_selection"]["safe_candidate_count"] == 2
    assert report["detector_selection"]["selected"]["model_path"] == "models/caleb_metal_panel.pt"
    assert report["detector_selection"]["selected"]["confidence"] == 0.10
    assert report["detector_selection"]["selected"]["label_recall"] == 1.0
    assert report["proof_readiness"]["status"] == "detector_seed_passes_but_worker_overlap_blocks_source_tokens"
    assert report["proof_readiness"]["dominant_failure_link"] == "worker_body_overlap"
    assert report["proof_readiness"]["selected_detector_positive_pass"] is True
    assert report["proof_readiness"]["has_safe_selected_detector"] is True
    assert report["failure_link_counts"] == {"missing_output_settle": 1, "worker_body_overlap": 2}
    assert report["worker_overlap_detail_counts"] == {"fully_entangled_with_worker": 2}
    assert report["diagnostics"][0]["failure_link_counts"] == {"missing_output_settle": 1, "worker_body_overlap": 2}
    assert report["diagnostics"][0]["worker_overlap_detail_counts"] == {"fully_entangled_with_worker": 2}
    assert report["decision_receipt_index"]["counts"] == {"accepted": 0, "suppressed": 2, "uncertain": 1}
    assert report["decision_receipt_index"]["suppressed"][0]["receipt_json_path"] == str(receipt)
    assert report["decision_receipt_index"]["suppressed"][0]["raw_crop_paths"] == ["diag/track_receipts/track-000001-crops/crop-01.jpg"]
    assert report["decision_receipt_index"]["uncertain"][0]["failure_link"] == "missing_output_settle"
    assert report["source_token_work_queue"]["item_count"] == 2
    assert report["source_token_work_queue"]["worker_overlap_detail_counts"] == {"fully_entangled_with_worker": 2}
    assert report["source_token_work_queue"]["top_items"][0]["worker_overlap_detail"] == "fully_entangled_with_worker"
    assert "do not count from the current box alone" in report["source_token_work_queue"]["top_items"][0]["recommended_action"]
    assert "Can any panel-shaped evidence be separated" in report["source_token_work_queue"]["top_items"][0]["audit_question"]
    assert report["source_token_work_queue"]["top_items"][0]["evidence_requirements_to_allow_source_token"] == [
        "person-mask or pose-aware crop evidence exposes a panel-like region inside the coarse person box",
        "panel evidence persists for several frames instead of appearing as a single noisy detector box",
        "the track can be separated from torso/arm motion before a source token is allowed",
    ]
    assert report["evidence_gap_matrix"]["dominant_gap"] == "panel_vs_worker_separation"
    assert report["evidence_gap_matrix"]["why_accepted_count_is_zero"] == "no perception-gate-approved source-token receipts"
    assert report["evidence_gap_matrix"]["blocked_receipts"] == 3
    assert report["evidence_gap_matrix"]["evidence_links"][0]["evidence_link"] == "panel_vs_worker_separation"
    assert report["evidence_gap_matrix"]["evidence_links"][0]["blocked_count"] == 2
    assert report["evidence_gap_matrix"]["evidence_links"][0]["bucket_counts"] == {"suppressed": 2}
    assert "discrete active panel" in report["evidence_gap_matrix"]["evidence_links"][0]["description"]
    assert report["evidence_gap_matrix"]["evidence_links"][1]["evidence_link"] == "output_entry_and_settle"
    assert any(item["receipt_json_path"] == str(receipt) for item in report["source_token_work_queue"]["top_items"])
    assert report["decision_receipt_index"]["missing_review_asset_counts"] == {
        "raw_crop_paths": 2,
        "receipt_card_path": 2,
        "receipt_json_path": 1,
    }
    track_receipt = report["diagnostics"][0]["track_decision_receipts"][0]
    assert track_receipt["failure_link"] == "worker_body_overlap"
    assert track_receipt["worker_overlap_detail"] == "fully_entangled_with_worker"
    assert track_receipt["receipt_json_path"] == str(receipt)
    assert track_receipt["raw_crop_paths"] == ["diag/track_receipts/track-000001-crops/crop-01.jpg"]


def test_build_report_counts_allowed_source_tokens(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {
            "allowed_source_token_tracks": [4, 9],
            "track_count": 3,
            "decision_counts": {"allow_source_token": 2, "reject": 1},
            "reason_counts": {"source_token_allowed_by_protrusion": 2, "worker_body_overlap": 1}
          }
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"items\": []}")

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report])

    assert report["verdict"] == "accepted_positive_count_available"
    assert report["accepted_count"] == 2
    assert report["suppressed_count"] == 1
    assert report["uncertain_count"] == 0
    assert report["bottleneck"] == "none"


def test_build_report_dedupes_overlapping_accepted_receipts_across_diagnostics(tmp_path: Path):
    receipt_a = tmp_path / "diag-a" / "track_receipts" / "track-000001.json"
    receipt_a.parent.mkdir(parents=True, exist_ok=True)
    receipt_a.write_text(
        """
        {
          "timestamps": {"first": 387.3, "last": 402.1},
          "review_assets": {"raw_crop_paths": ["diag-a/crop-a.jpg"]}
        }
        """,
        encoding="utf-8",
    )
    receipt_b = tmp_path / "diag-b" / "track_receipts" / "track-000002.json"
    receipt_b.parent.mkdir(parents=True, exist_ok=True)
    receipt_b.write_text(
        """
        {
          "timestamps": {"first": 398.081, "last": 402.081},
          "review_assets": {"raw_crop_paths": ["diag-b/crop-b.jpg"]}
        }
        """,
        encoding="utf-8",
    )
    diagnostic_a = write_json(
        tmp_path / "diag-a" / "diagnostic.json",
        f"""
        {{
          "video_path": "data/videos/from-pc/factory2.MOV",
          "start_timestamp": 372.0,
          "end_timestamp": 412.0,
          "perception_gate_summary": {{
            "allowed_source_token_tracks": [1],
            "track_count": 1,
            "decision_counts": {{"allow_source_token": 1}},
            "reason_counts": {{"moving_panel_candidate": 1}}
          }},
          "perception_gate": [
            {{
              "track_id": 1,
              "decision": "allow_source_token",
              "reason": "moving_panel_candidate",
              "flags": ["source_token_allowed_by_person_panel_separation"],
              "evidence": {{"source_frames": 9, "output_frames": 2}}
            }}
          ],
          "track_receipts": ["{receipt_a}"],
          "track_receipt_cards": []
        }}
        """,
    )
    diagnostic_b = write_json(
        tmp_path / "diag-b" / "diagnostic.json",
        f"""
        {{
          "video_path": "data/videos/from-pc/factory2.MOV",
          "start_timestamp": 396.0,
          "end_timestamp": 427.0,
          "perception_gate_summary": {{
            "allowed_source_token_tracks": [2],
            "track_count": 1,
            "decision_counts": {{"allow_source_token": 1}},
            "reason_counts": {{"moving_panel_candidate": 1}}
          }},
          "perception_gate": [
            {{
              "track_id": 2,
              "decision": "allow_source_token",
              "reason": "moving_panel_candidate",
              "flags": ["source_token_allowed_by_person_panel_separation"],
              "evidence": {{"source_frames": 1, "output_frames": 1}}
            }}
          ],
          "track_receipts": ["{receipt_b}"],
          "track_receipt_cards": []
        }}
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"items\": []}")

    report = build_report(diagnostic_paths=[diagnostic_a, diagnostic_b], fp_report_paths=[fp_report])

    assert report["verdict"] == "accepted_positive_count_available"
    assert report["accepted_count"] == 1
    assert report["accepted_receipt_count"] == 2
    assert report["accepted_duplicate_receipt_count"] == 1
    accepted = report["decision_receipt_index"]["accepted"]
    assert len(accepted) == 2
    assert accepted[0]["accepted_cluster_id"] == accepted[1]["accepted_cluster_id"]
    assert accepted[0]["counts_toward_accepted_total"] is True
    assert accepted[1]["counts_toward_accepted_total"] is False


def test_build_report_rehydrates_gate_with_person_panel_separation_receipt(tmp_path: Path):
    receipt = tmp_path / "diag" / "track_receipts" / "track-000005.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        """
        {
          "review_assets": {
            "track_sheet_path": "diag/track_receipts/track-000005-sheet.jpg",
            "raw_crop_paths": ["diag/track_receipts/track-000005-crops/crop-01-source.jpg"]
          }
        }
        """,
        encoding="utf-8",
    )
    separation = receipt.with_name("track-000005-person-panel-separation.json")
    separation.write_text(
        """
        {
          "packet_id": "event0002-track000005",
          "diagnostic_only": true,
          "recommendation": "countable_panel_candidate",
          "summary": {
            "frame_count": 3,
            "separable_panel_candidate_frames": 3,
            "worker_body_overlap_frames": 0,
            "static_or_background_edge_frames": 0,
            "max_visible_nonperson_ratio": 0.542531,
            "max_estimated_visible_signal": 0.075512
          },
          "selected_frames": [
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "source", "separation_decision": "separable_panel_candidate"},
            {"zone": "output", "separation_decision": "separable_panel_candidate"}
          ]
        }
        """,
        encoding="utf-8",
    )
    weak_receipt = tmp_path / "diag" / "track_receipts" / "track-000007.json"
    weak_receipt.write_text('{"review_assets": {"raw_crop_paths": []}}', encoding="utf-8")
    weak_receipt.with_name("track-000007-person-panel-separation.json").write_text(
        """
        {
          "packet_id": "event0002-track000007",
          "diagnostic_only": true,
          "recommendation": "insufficient_visibility",
          "summary": {
            "frame_count": 1,
            "separable_panel_candidate_frames": 1,
            "worker_body_overlap_frames": 0,
            "static_or_background_edge_frames": 0,
            "max_visible_nonperson_ratio": 0.491658,
            "max_estimated_visible_signal": 0.048451
          },
          "selected_frames": [
            {"zone": "source", "separation_decision": "separable_panel_candidate"}
          ]
        }
        """,
        encoding="utf-8",
    )

    diagnostic = write_json(
        tmp_path / "diag" / "diagnostic.json",
        f"""
        {{
          "schema_version": "factory-event-diagnostic-v1",
          "video_path": "data/videos/from-pc/factory2.MOV",
          "start_timestamp": 78.0,
          "end_timestamp": 118.0,
          "fps": 3.0,
          "frame_count": 120,
          "overlay_sheet_path": "diag/overlay_sheet.jpg",
          "overlay_video_path": "diag/overlay_video.mp4",
          "perception_gate_summary": {{
            "allowed_source_token_tracks": [],
            "track_count": 2,
            "decision_counts": {{"allow_source_token": 0, "reject": 2}},
            "reason_counts": {{"worker_body_overlap": 2}}
          }},
          "perception_gate": [
            {{
              "track_id": 5,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap", "not_enough_object_outside_person"],
              "evidence": {{
                "track_id": 5,
                "detections": 39,
                "first_zone": "source",
                "zones_seen": ["source", "output"],
                "source_frames": 38,
                "output_frames": 1,
                "max_displacement": 603.294,
                "mean_internal_motion": 0.337425,
                "max_internal_motion": 0.730217,
                "person_overlap_ratio": 1.0,
                "outside_person_ratio": 0.0,
                "static_stack_overlap_ratio": 0.0,
                "static_location_ratio": 0.333333,
                "flow_coherence": 0.501419,
                "edge_like_ratio": 0.0
              }}
            }},
            {{
              "track_id": 7,
              "decision": "reject",
              "reason": "worker_body_overlap",
              "flags": ["high_person_overlap", "not_enough_object_outside_person"],
              "evidence": {{
                "track_id": 7,
                "detections": 1,
                "first_zone": "source",
                "zones_seen": ["source"],
                "source_frames": 1,
                "output_frames": 0,
                "max_displacement": 22.0,
                "mean_internal_motion": 0.11,
                "max_internal_motion": 0.24,
                "person_overlap_ratio": 0.708349,
                "outside_person_ratio": 0.291651,
                "static_stack_overlap_ratio": 0.0,
                "static_location_ratio": 0.0,
                "flow_coherence": 0.2,
                "edge_like_ratio": 0.0
              }}
            }}
          ],
          "track_receipts": ["{receipt}", "{weak_receipt}"],
          "track_receipt_cards": []
        }}
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", '{"items": []}')

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report])

    assert report["accepted_count"] == 1
    assert report["suppressed_count"] == 1
    assert report["verdict"] == "accepted_positive_count_available"
    accepted = report["decision_receipt_index"]["accepted"][0]
    suppressed = report["decision_receipt_index"]["suppressed"][0]
    assert accepted["track_id"] == 5
    assert accepted["person_panel_separation_path"] == str(separation)
    assert suppressed["track_id"] == 7
    promoted_track = next(item for item in report["diagnostics"][0]["track_decision_receipts"] if item["track_id"] == 5)
    assert promoted_track["decision"] == "allow_source_token"
    assert promoted_track["reason"] == "moving_panel_candidate"
    assert promoted_track["failure_link"] == "source_token_approved"


def test_build_report_dedupes_non_overlapping_receipts_that_reuse_same_source_lineage(tmp_path: Path):
    receipt_a = tmp_path / "diag" / "track_receipts" / "track-000001.json"
    receipt_a.parent.mkdir(parents=True, exist_ok=True)
    receipt_a.write_text(
        """
        {
          "timestamps": {"first": 300.2, "last": 303.7},
          "review_assets": {"raw_crop_paths": ["diag/crop-a.jpg"]}
        }
        """,
        encoding="utf-8",
    )
    receipt_b = tmp_path / "diag" / "track_receipts" / "track-000002.json"
    receipt_b.write_text(
        """
        {
          "timestamps": {"first": 305.2, "last": 306.1},
          "review_assets": {"raw_crop_paths": ["diag/crop-b.jpg"]}
        }
        """,
        encoding="utf-8",
    )
    diagnostic = write_json(
        tmp_path / "diag" / "diagnostic.json",
        f"""
        {{
          "video_path": "data/videos/from-pc/factory2.MOV",
          "start_timestamp": 288.0,
          "end_timestamp": 328.0,
          "perception_gate_summary": {{
            "allowed_source_token_tracks": [1, 2],
            "track_count": 2,
            "decision_counts": {{"allow_source_token": 2}},
            "reason_counts": {{"moving_panel_candidate": 2}}
          }},
          "perception_gate": [
            {{
              "track_id": 1,
              "decision": "allow_source_token",
              "reason": "moving_panel_candidate",
              "flags": ["source_token_allowed_by_crop_classifier"],
              "evidence": {{"source_frames": 5, "output_frames": 1}}
            }},
            {{
              "track_id": 2,
              "decision": "allow_source_token",
              "reason": "moving_panel_candidate",
              "flags": ["source_token_allowed_by_crop_classifier"],
              "evidence": {{
                "source_frames": 0,
                "output_frames": 1,
                "merged_predecessor_track_id": 1,
                "merged_predecessor_track_ids": [1],
                "merged_predecessor_receipt_paths": ["{receipt_a}"]
              }}
            }}
          ],
          "track_receipts": ["{receipt_a}", "{receipt_b}"],
          "track_receipt_cards": []
        }}
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"items\": []}")

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report])

    assert report["accepted_count"] == 1
    assert report["accepted_receipt_count"] == 2
    assert report["accepted_duplicate_receipt_count"] == 1
    accepted = report["decision_receipt_index"]["accepted"]
    assert accepted[0]["source_token_key"] == accepted[1]["source_token_key"]
    assert accepted[0]["counts_toward_accepted_total"] is True
    assert accepted[1]["counts_toward_accepted_total"] is False
    assert accepted[1]["accepted_duplicate_reasons"] == ["shared_source_token_key"]


def test_worker_overlap_details_separate_entangled_from_protruding(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {
            "allowed_source_token_tracks": [3],
            "track_count": 3,
            "decision_counts": {"allow_source_token": 1, "reject": 2},
            "reason_counts": {"moving_panel_candidate": 1, "worker_body_overlap": 2}
          },
          "perception_gate": [
            {"track_id": 1, "decision": "reject", "reason": "worker_body_overlap", "flags": ["high_person_overlap", "not_enough_object_outside_person"], "evidence": {"person_overlap_ratio": 0.95, "outside_person_ratio": 0.05}},
            {"track_id": 2, "decision": "reject", "reason": "worker_body_overlap", "flags": ["high_person_overlap", "person_overlap_with_panel_protrusion"], "evidence": {"person_overlap_ratio": 0.85, "outside_person_ratio": 0.40}},
            {"track_id": 3, "decision": "allow_source_token", "reason": "moving_panel_candidate", "flags": ["source_token_allowed_by_protrusion"], "evidence": {"person_overlap_ratio": 0.78, "outside_person_ratio": 0.38}}
          ]
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"items\": []}")

    report = build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report])

    assert report["worker_overlap_detail_counts"] == {
        "allowed_by_protrusion": 1,
        "fully_entangled_with_worker": 1,
        "protrusion_candidate_not_approved": 1,
    }


def test_render_markdown_includes_receipt_paths(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {"allowed_source_token_tracks": [], "track_count": 1, "decision_counts": {"reject": 1}, "reason_counts": {"worker_body_overlap": 1}},
          "perception_gate": [{"track_id": 1, "decision": "reject", "reason": "worker_body_overlap", "flags": ["high_person_overlap"], "evidence": {"person_overlap_ratio": 0.9, "outside_person_ratio": 0.1}}],
          "track_receipts": ["receipts/track-1.json"],
          "overlay_sheet_path": "overlay.jpg"
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"hard_negative_images\": 1, \"false_positive_detections\": 0}")
    markdown = render_markdown(build_report(diagnostic_paths=[diagnostic], fp_report_paths=[fp_report]))

    assert "accepted_count: 0" in markdown
    assert "Proof readiness" in markdown
    assert "Decision receipt index" in markdown
    assert "Source-token work queue" in markdown
    assert "Evidence gap matrix" in markdown
    assert "panel_vs_worker_separation" in markdown
    assert "why_accepted_count_is_zero" in markdown
    assert "Highest-priority worker-entangled receipts" in markdown
    assert "do not count from the current box alone" in markdown
    assert "audit_question" in markdown
    assert "evidence_required" in markdown
    assert "person-mask or pose-aware crop evidence" in markdown
    assert "Suppressed receipt samples" in markdown
    assert "worker_overlap_details" in markdown
    assert "receipts/track-1.json" in markdown
    assert "overlay.jpg" in markdown


def test_source_token_key_prefers_runtime_source_token_id() -> None:
    key = source_token_key(
        track_id=7,
        receipt_path="data/diagnostics/runtime-proof/final-two/track_receipts/track-000007.json",
        row={
            "evidence": {
                "runtime_source_token_id": "source-token-42",
                "merged_predecessor_track_ids": [3],
            }
        },
    )

    assert key == "runtime-source-token:source-token-42"


def test_main_writes_json_and_markdown(tmp_path: Path):
    diagnostic = write_json(
        tmp_path / "diagnostic.json",
        """
        {
          "perception_gate_summary": {"allowed_source_token_tracks": [], "track_count": 1, "decision_counts": {"uncertain": 1}, "reason_counts": {"source_without_output_settle": 1}}
        }
        """,
    )
    fp_report = write_json(tmp_path / "fp.json", "{\"hard_negative_images\": 1, \"false_positive_detections\": 0}")
    positive_report = write_json(tmp_path / "positive.json", "{\"summary\": {\"positive_labels\": 1, \"matched_labels\": 1, \"missed_labels\": 0, \"label_recall\": 1.0}}")
    output = tmp_path / "report.json"
    markdown = tmp_path / "report.md"

    assert main([
        "--diagnostic",
        str(diagnostic),
        "--fp-report",
        str(fp_report),
        "--positive-report",
        str(positive_report),
        "--output",
        str(output),
        "--markdown-output",
        str(markdown),
    ]) == 0

    assert output.exists()
    assert markdown.exists()
    assert "auditable_abstention" in output.read_text(encoding="utf-8")
