# factory2 Research Scripts — Manifest

62 Python scripts from the YOLO-era factory2 research sprint (April–June
2026), kept for provenance. **None of these are current tooling** — the live
Track B surface is `../CURRENT.md`.

Status legend: DEAD = superseded relic, do not run. HISTORICAL = worked once
against data that has since moved; kept as evidence of how a result was
produced. ABSORBED = logic now lives in app/services or a current script.

| Script | Status | Notes |
| --- | --- | --- |
| run_clip_eval.py | DEAD | YOLO-era eval; the current exam is `scripts/run_clip_exam.py` |
| validate_miner_recall.py | HISTORICAL | recall bar (6/7) now owned by the exam kernel contract; current: scripts/validate_tripwire_recall.py |
| build_holdout_case.py | ABSORBED | still invoked by onboarding_rehearsal "split" stage |
| apply_live_activation.py | HISTORICAL | one-time June activation |

NOTE: only the four rows above are classified so far. Every row in the
auto-generated inventory below has status `?` — classify during the next
docs/scripts sweep. Nothing in this directory is current tooling regardless
of status.

## Inventory (auto-generated 2026-08-22)

| __init__.py | ? | 1 lines |
| analyze_factory2_runtime_truth_gap.py | ? | 256 lines |
| analyze_panel_crop_evidence.py | ? | 237 lines |
| apply_factory2_track_review_labels.py | ? | 148 lines |
| apply_img2628_event_dispute_decisions.py | ? | 315 lines |
| apply_live_activation.py | ? | 56 lines |
| assemble_active_panel_dataset.py | ? | 330 lines |
| auto_prelabel_active_panel.py | ? | 291 lines |
| build_day1_exam_gate.py | ? | 127 lines |
| build_factory2_crop_training_dataset.py | ? | 302 lines |
| build_factory2_divergent_chain_review.py | ? | 435 lines |
| build_factory2_final_gap_search_plan.py | ? | 182 lines |
| build_factory2_final_gap_search_report.py | ? | 184 lines |
| build_factory2_final_two_chain_adjudication.py | ? | 451 lines |
| build_factory2_final_two_rescue_dataset.py | ? | 262 lines |
| build_factory2_human_truth_ledger.py | ? | 175 lines |
| build_factory2_proof_alignment_queue.py | ? | 176 lines |
| build_factory2_recall_work_queue.py | ? | 229 lines |
| build_factory2_runtime_backed_proof_set.py | ? | 90 lines |
| build_factory2_runtime_event_receipt_packets.py | ? | 267 lines |
| build_factory2_runtime_lineage_diagnostic.py | ? | 608 lines |
| build_factory2_synthetic_lineage_report.py | ? | 184 lines |
| build_failed_blind_run_learning_packet.py | ? | 455 lines |
| build_holdout_case.py | ? | 122 lines |
| build_img2628_diagnostic_active_panel_dataset.py | ? | 282 lines |
| build_img2628_motion_score_event_dataset.py | ? | 281 lines |
| build_img2628_placement_action_dataset.py | ? | 290 lines |
| build_img2628_placement_action_multiclass_dataset.py | ? | 315 lines |
| build_morning_proof_report.py | ? | 1214 lines |
| build_panel_transfer_review_packets.py | ? | 294 lines |
| build_real_factory_diagnostic_action_dataset.py | ? | 429 lines |
| build_review_queue.py | ? | 183 lines |
| convert_failed_blind_run_review.py | ? | 573 lines |
| convert_truth_review_worksheet_to_csv.py | ? | 167 lines |
| derive_auto_station_calibration.py | ? | 49 lines |
| diagnose_event_window.py | ? | 1482 lines |
| export_factory2_blocked_crops.py | ? | 235 lines |
| export_factory2_static_resident_reference_crops.py | ? | 113 lines |
| export_factory2_worker_reference_crops.py | ? | 232 lines |
| export_hard_negatives.py | ? | 208 lines |
| export_onboarding_stable_negatives.py | ? | 150 lines |
| export_review_queue_html.py | ? | 208 lines |
| export_truth_review_form_html.py | ? | 274 lines |
| extract_onboarding_windows.py | ? | 38 lines |
| freeze_factory2_diagnostics.py | ? | 124 lines |
| generate_onboarding_teacher_labels.py | ? | 36 lines |
| mine_event_clips.py | ? | 482 lines |
| mine_hard_negative_frames.py | ? | 74 lines |
| optimize_factory2_proof_set.py | ? | 229 lines |
| package_factory2_crop_review.py | ? | 216 lines |
| reconstruct_factory2_truth_candidates.py | ? | 275 lines |
| review_labels_ai.py | ? | 164 lines |
| run_blind_replay_gate.py | ? | 44 lines |
| run_clip_eval.py | ? | 608 lines |
| run_factory2_final_gap_search.py | ? | 164 lines |
| run_factory2_morning_proof.py | ? | 308 lines |
| run_factory_day1_pipeline.py | ? | 383 lines |
| run_periodic_audit.py | ? | 47 lines |
| run_yolo26_training_eval.py | ? | 58 lines |
| validate_miner_recall.py | ? | 251 lines |
| validate_zone_mining.py | ? | 160 lines |
| write_station_calibration.py | ? | 40 lines |
