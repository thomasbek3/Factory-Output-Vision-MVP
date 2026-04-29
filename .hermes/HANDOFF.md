# Factory Vision Hermes Handoff

Updated: 2026-04-29 03:31:14 EDT
Repo: `/Users/thomas/Projects/Factory-Output-Vision-MVP`
Branch: `main`

## 2026-04-29: Factory2 Synthetic Count Authority Hardened

Implemented the next honest Factory2 slice after the runtime/proof divergence audit:

```text
app/services/count_state_machine.py
app/services/runtime_event_counter.py
scripts/audit_factory2_runtime_events.py
scripts/build_factory2_synthetic_lineage_report.py
scripts/build_factory2_final_gap_search_plan.py
tests/test_count_state_machine.py
tests/test_runtime_event_counter.py
tests/test_audit_factory2_runtime_events.py
tests/test_build_factory2_synthetic_lineage_report.py
tests/test_build_factory2_final_gap_search_plan.py
AGENTS.md
CLAUDE.md
tasks/lessons.md
docs/superpowers/plans/2026-04-29-factory2-synthetic-lineage-convergence.md
```

What changed:

```text
- Added `count_authority` to `CountEvent` with:
  - `source_token_authorized`
  - `runtime_inferred_only`
- Synthetic `approved_delivery_chain` events no longer mint fake source-token evidence from the output bbox.
- `CountStateMachine` now tracks:
  - `source_token_authorized_event_count`
  - `runtime_inferred_only_event_count`
- Runtime audit rows now emit:
  - `count_authority`
  - `predecessor_chain_track_ids`
  - source/output observation counts
- Added a synthetic-lineage report that classifies runtime approved-chain events by proof overlap and source-gap behavior.
- Fixed the final-gap search planner so unresolved proof gaps use source-history-driven windows instead of arbitrary short lead windows.
```

Real artifacts created:

```text
Reports:
- data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json
- data/reports/factory2_final_gap_search_plan.v2.json
- data/reports/factory2_final_gap_search_run.v2.event0007.json
- data/reports/factory2_final_gap_search_report.v2.event0007.json
- data/reports/factory2_final_gap_search_run.v2.event0008.json
- data/reports/factory2_final_gap_search_report.v2.event0008.json
- data/reports/factory2_final_gap_search_summary.v2.json
- data/reports/factory2_count_authority_ledger.v1.json

Targeted post-hardening runtime audits:
- data/reports/factory2_runtime_event_audit.lineage_280_308.v4.json
- data/reports/factory2_runtime_event_audit.lineage_398_427.v4.json
```

Current truthful state:

```text
Runtime/app path:
- still operationally counts Factory2 to the human truth target of 23

Proof path:
- remains at accepted_count = 21

Authority ledger:
- runtime_inferred_total: 23
- proof_accepted_total: 21
- inherited_live_source_token_count: 11
- synthetic_with_overlapping_proof_count: 10
- synthetic_without_distinct_proof_count: 2
- unresolved runtime-inferred-only timestamps:
  - 305.708s
  - 425.012s
```

Why this matters:

```text
The repo now distinguishes operational runtime counts from source-token-backed proof authority.
The remaining two proof gaps are no longer “maybe more window tuning” cases:
- both corrected source-history-driven rescue searches still collapsed into
  `shared_source_lineage_no_distinct_proof_receipt`
- Oracle explicitly recommended preserving runtime 23 / proof 21 as the honest state on current evidence
- the right hardening move was to stop fabricating source-token-shaped evidence for synthetic runtime counts
```

Oracle result:

```text
Oracle slug: factory2-synthetic-next-step

Recommendation:
- preserve runtime 23 / proof 21 as the honest state
- do not keep tuning proof windows for 305.708s / 425.012s
- harden semantics so synthetic approved-chain events are runtime-inferred only,
  not source-token-backed proof authority

That recommendation is now reflected in code and doctrine.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_factory2_synthetic_lineage_report.py -q
.venv/bin/python -m pytest tests/test_build_factory2_final_gap_search_plan.py -q
.venv/bin/python scripts/build_factory2_synthetic_lineage_report.py --runtime-audit data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json --proof-report data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json --divergence data/reports/factory2_proof_runtime_divergence.final_two_v2.json --output data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json --force
.venv/bin/python scripts/build_factory2_final_gap_search_plan.py --packets data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json --lineage-report data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json --output data/reports/factory2_final_gap_search_plan.v2.json --lead-seconds 4 --lead-seconds 6 --lead-seconds 8 --lead-seconds 10 --lead-seconds 12 --tail-seconds 2 --tail-seconds 3 --tail-seconds 4 --tail-seconds 6 --fps 5 --fps 8 --fps 10 --force
.venv/bin/python scripts/run_factory2_final_gap_search.py --plan data/reports/factory2_final_gap_search_plan.v2.json --output data/reports/factory2_final_gap_search_run.v2.event0007.json --event-id factory2-runtime-only-0007 --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --person-model yolo11n.pt --force
.venv/bin/python scripts/build_factory2_final_gap_search_report.py --search-run data/reports/factory2_final_gap_search_run.v2.event0007.json --output data/reports/factory2_final_gap_search_report.v2.event0007.json --force
.venv/bin/python scripts/run_factory2_final_gap_search.py --plan data/reports/factory2_final_gap_search_plan.v2.json --output data/reports/factory2_final_gap_search_run.v2.event0008.json --event-id factory2-runtime-only-0008 --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --person-model yolo11n.pt --force
.venv/bin/python scripts/build_factory2_final_gap_search_report.py --search-run data/reports/factory2_final_gap_search_run.v2.event0008.json --output data/reports/factory2_final_gap_search_report.v2.event0008.json --force
.venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py tests/test_build_factory2_synthetic_lineage_report.py tests/test_build_factory2_final_gap_search_plan.py tests/test_run_factory2_final_gap_search.py tests/test_build_factory2_final_gap_search_report.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_morning_proof_report.py -q
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_280_308.v4.json --start-seconds 280 --end-seconds 308 --processing-fps 10 --include-track-histories --force
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_398_427.v4.json --start-seconds 398 --end-seconds 427 --processing-fps 10 --include-track-histories --force
oracle --slug factory2-synthetic-next-step ...
```

Verification:

```text
54 tests passed on the affected suite after the hardening change.
Targeted runtime audit around ~305.7s now emits:
- provenance_status = synthetic_approved_chain_token
- count_authority = runtime_inferred_only
- source_token_id = null
- source_bbox = null

Targeted runtime audit around ~425.0s now emits:
- provenance_status = synthetic_approved_chain_token
- count_authority = runtime_inferred_only
- source_token_id = null
- source_bbox = null

Corrected 5/8/10fps rescue searches for both remaining proof gaps all still scored:
- shared_source_lineage_no_distinct_proof_receipt
```

Next blocker:

```text
There is no remaining honest proof-window tuning move on current evidence.
The remaining blocker is product semantics / product presentation:
- what user-facing number should represent proof-backed counts
- whether the product needs to expose the runtime/proof split directly
```

Exact next recommended step:

```text
Do not keep tuning proof windows for 305.708s / 425.012s.
If product semantics matter next, thread `count_authority` through the event ledger / API layer and expose:
- runtime inferred total
- proof-backed total
- unresolved runtime-inferred-only count
```

## 2026-04-29: Factory2 Runtime Lineage Audit Closed The Final Two

Implemented the runtime-lineage audit path Oracle asked for and used it to settle the two remaining proof/runtime gaps:

```text
app/services/count_state_machine.py
app/services/runtime_event_counter.py
scripts/audit_factory2_runtime_events.py
scripts/build_factory2_runtime_lineage_diagnostic.py
scripts/build_morning_proof_report.py
tests/test_count_state_machine.py
tests/test_audit_factory2_runtime_events.py
tests/test_build_factory2_runtime_lineage_diagnostic.py
tests/test_build_morning_proof_report.py
AGENTS.md
CLAUDE.md
tasks/lessons.md
```

What changed:

```text
- Added explicit runtime source-token provenance to `CountEvent`.
- `approved_delivery_chain` events now distinguish `inherited_live_source_token` from `synthetic_approved_chain_token`.
- Extended the runtime audit script to emit source-token provenance and full per-track histories.
- Added a runtime-lineage diagnostic builder that can turn audited runtime events into proof-style receipts.
- Guarded the runtime-lineage proof builder so synthetic approved-chain fallback events are rejected instead of being promoted into proof.
```

Real artifacts created:

```text
Runtime provenance audits:
- data/reports/factory2_runtime_event_audit.lineage_0_308.json
- data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json

Runtime-lineage diagnostics:
- data/diagnostics/runtime-proof/factory2-runtime-only-0007-lineage-v2/diagnostic.json
- data/diagnostics/runtime-proof/factory2-runtime-only-0008-lineage-v1/diagnostic.json

Proof artifacts:
- data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json
- data/reports/factory2_proof_runtime_divergence.final_two_v2.json
```

Final result from the lineage audit:

```text
Runtime/app path:
- still reaches 23 on the patched from-start audit

Proof path:
- remains at accepted_count = 21

Why proof stays at 21:
- `305.708s` -> provenance_status = synthetic_approved_chain_token
- `425.012s` -> provenance_status = synthetic_approved_chain_token

Conclusion:
- both remaining runtime-only events are runtime-discovered counts,
- but they are not honest proof receipts,
- so the correct repo state is runtime 23 / proof 21.
```

Oracle result:

```text
Oracle confirmed the right move was from-start runtime provenance, not more proof-window threshold/fps tweaks.
It also specifically warned that synthetic approved-chain fallback tokens are not proof-eligible.
That warning held up against the real patched lineage artifact.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_audit_factory2_runtime_events.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_morning_proof_report.py -q
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_0_308.json --start-seconds 0 --end-seconds 308 --processing-fps 10 --include-track-histories --force
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json --start-seconds 0 --end-seconds 430 --processing-fps 10 --include-track-histories --force
.venv/bin/python - <<'PY'
# built runtime-lineage diagnostics for 305.708s and 425.012s from the 0-430 audit
PY
.venv/bin/python - <<'PY'
# rebuilt proof report with both runtime-lineage diagnostics included
PY
/opt/homebrew/bin/oracle --slug factory2-lineage-path ...
```

Verification:

```text
28 tests passed on the touched suites.
Patched runtime-lineage audit to 430s finished at final_count = 23.
Both runtime-lineage diagnostics now reject synthetic fallback counts.
Rebuilt proof report stayed at accepted_count = 21.
```

Next blocker:

```text
There is no remaining proof-window tuning blocker. The remaining blocker is product semantics:
- either accept runtime 23 / proof 21 as the honest state,
- or change the runtime approved-delivery-chain policy so synthetic fallback tokens no longer create runtime-only count authority.
```

Exact next recommended step:

```text
Do not spend more time on narrower proof windows. If the product needs proof and runtime to converge, refactor `commit_approved_delivery_chain` so `synthetic_approved_chain_token` is either disallowed for counting or separated into an explicit runtime-only category with different product semantics.
```


## Factory2 crop review package + training interface — 2026-04-28 21:06 EDT

Implemented the next labeling/training slice:

```text
scripts/package_factory2_crop_review.py
scripts/build_factory2_crop_training_dataset.py
tests/test_package_factory2_crop_review.py
tests/test_build_factory2_crop_training_dataset.py
docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md
tasks/lessons.md
```

What changed:

```text
- Added a label-ready crop review packager that turns the frozen blocked-crop dataset into a flat image bundle plus manifest, writable CSV, classes list, and README for local review or later private Roboflow upload.
- Review items are ranked by labeling priority:
  - `p0_candidate_salvage`
  - `p1_visibility_review`
  - `p2_negative_confirmation`
  - `p3_positive_boundary`
- Added a deterministic crop-training dataset builder that consumes the package manifest plus review CSV and emits a classifier-oriented dataset manifest with track-level train/val/test grouping.
- The training manifest records explicit integration targets back into the proof/runtime gate and reports whether the label set is actually ready for a second-stage model.
```

Real artifacts created:

```text
Review package:
- data/reports/factory2_crop_review_package.narrow_frozen_v2.json
- data/datasets/factory2_crop_review_package_narrow_frozen_v2/

Current review-package counts:
- total items: 218
- p0_candidate_salvage: 90
- p1_visibility_review: 1
- p2_negative_confirmation: 32
- p3_positive_boundary: 95

Training interface artifact:
- data/reports/factory2_crop_training_dataset.narrow_frozen_v2.json
- data/datasets/factory2_crop_training_dataset_narrow_frozen_v2/

Current training-interface status from placeholder labels:
- eligible_item_count: 95
- skipped_unclear_count: 123
- label_counts: carried_panel=95
- missing_classes: worker_only, static_stack
- ready_for_training: false
```

Why this matters:

```text
The repo no longer stops at “we should label crops.” It now has the full label handoff and the immediate model-ingest contract on disk. The blocker is explicit and auditable: the current package still lacks reviewed `worker_only` and `static_stack` labels, so training would be premature.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py -q
.venv/bin/python -m py_compile scripts/package_factory2_crop_review.py scripts/build_factory2_crop_training_dataset.py tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_export_factory2_blocked_crops.py tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py -q
.venv/bin/python scripts/package_factory2_crop_review.py --crop-dataset-report data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json --output-report data/reports/factory2_crop_review_package.narrow_frozen_v2.json --package-dir data/datasets/factory2_crop_review_package_narrow_frozen_v2 --force
.venv/bin/python scripts/build_factory2_crop_training_dataset.py --review-package-report data/reports/factory2_crop_review_package.narrow_frozen_v2.json --output-report data/reports/factory2_crop_training_dataset.narrow_frozen_v2.json --dataset-dir data/datasets/factory2_crop_training_dataset_narrow_frozen_v2 --force
```

Verification:

```text
40 tests passed
py_compile passed
real review package exists on disk
real training-interface report exists on disk and correctly reports not-ready status until blocked crops are labeled
```

Next blocker:

```text
The blocker is now externalized to label truth, not pipeline code. The repo needs reviewed labels for the 90 `p0_candidate_salvage` crops first, then `p2_negative_confirmation`, so the second-stage crop classifier has both positive and negative classes.
```

Exact next recommended step:

```text
Open `data/datasets/factory2_crop_review_package_narrow_frozen_v2/review_labels.csv`, label the `p0_candidate_salvage` rows first as `carried_panel | worker_only | static_stack`, rerun `scripts/build_factory2_crop_training_dataset.py`, and do not start model training until `ready_for_training` flips true.
```


## Factory2 blocked crop dataset export — 2026-04-28 20:16 EDT

Implemented the next recall-training slice:

```text
scripts/export_factory2_blocked_crops.py
tests/test_export_factory2_blocked_crops.py
```

What changed:

```text
- Added a crop exporter that reads the frozen merged proof report decision receipt index and emits a label-ready dataset manifest plus copied crop assets.
- Blocked worker-overlap receipts are exported as `blocked_worker_overlap`.
- Canonical accepted carries are also exported as `accepted_positive_boundary` so the future training set has both sides of the decision boundary.
- Each exported crop item preserves provenance: diagnostic/window, track id, timestamp, zone, gate decision/reason, person overlap, outside-person ratio, separation recommendation, receipt paths, and a label placeholder.
```

Real artifact created:

```text
Manifest:
- data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json

Dataset directory:
- data/datasets/factory2_blocked_crops_narrow_frozen_v2/

Counts:
- blocked_track_count: 29
- blocked_crop_count: 123
- positive_track_count: 12
- positive_crop_count: 95
- total exported items: 218
```

Why this matters:

```text
The next blocker is no longer missing crop plumbing. The repo now has a concrete, provenance-preserving dataset built directly from the frozen merged proof state. That makes panel-vs-worker labeling and second-stage training possible without hand-curating files from receipt directories.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_export_factory2_blocked_crops.py -q
.venv/bin/python -m py_compile scripts/export_factory2_blocked_crops.py tests/test_export_factory2_blocked_crops.py
.venv/bin/python scripts/export_factory2_blocked_crops.py --proof-report data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --output-report data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json --dataset-dir data/datasets/factory2_blocked_crops_narrow_frozen_v2 --force
```

Verification:

```text
36 tests passed
py_compile passed
real blocked crop dataset artifact exists on disk with copied crops and manifest
```

Next blocker:

```text
The remaining blocker is no longer exporter plumbing; it is turning the 123 blocked worker-overlap crops into labeled training evidence and then feeding that second-stage signal back into the proof/runtime gate.
```

Exact next recommended step:

```text
Label the highest-priority blocked crops first, starting with the frozen merged worker-overlap receipts that already have `countable_panel_candidate` person/panel recommendations but still failed the gate.
```


## Factory2 frozen narrow merged proof set + accepted dedupe — 2026-04-28 20:01 EDT

Implemented the next recall-proof slice:

```text
AGENTS.md
CLAUDE.md
scripts/freeze_factory2_diagnostics.py
scripts/build_morning_proof_report.py
scripts/run_factory2_morning_proof.py
tests/test_freeze_factory2_diagnostics.py
tests/test_build_morning_proof_report.py
tests/test_run_factory2_morning_proof.py
tasks/lessons.md
```

What changed:

```text
- Added `freeze_factory2_diagnostics.py` to copy selected diagnostic directories into an isolated frozen tree and rewrite all embedded JSON asset paths so merged proof runs stop mutating the shared source diagnostics.
- Added `--freeze-diagnostics-dir` support to `scripts/run_factory2_morning_proof.py`, and the run summary now records both source diagnostics and frozen diagnostics.
- Added report-layer accepted-receipt deduping: overlapping accepted receipts across windows now remain visible for audit, but only one canonical receipt per overlapping interval cluster contributes to the top-level `accepted_count`.
```

Real merged narrow-proof result:

```text
Frozen merged proof command completed on:
data/diagnostics/frozen/factory2-narrow-merged-v2

Raw accepted receipts: 13
Distinct accepted_count after overlap dedupe: 12
Suppressed_count: 27
Uncertain_count: 13
Verdict: accepted_positive_count_available

Artifacts:
- data/reports/factory2_morning_proof_report.narrow_frozen_v2.json
- data/reports/factory2_morning_proof_report.narrow_frozen_v2.md
- data/reports/factory2_transfer_review_packets.narrow_frozen_v2.json
- data/reports/factory2_person_panel_separation.narrow_frozen_v2.json
```

Per-window accepted counts in the frozen merged set:

```text
0–30s        -> 1
98s anchor   -> 1
145–185s     -> 1
222s window  -> 2
232–272s     -> 2
288–328s     -> 1
332–372s     -> 1
372–412s     -> 2
418s tail    -> 2 raw receipts, but one overlaps the 372–412 accepted carry and is deduped out of the top-level total
```

Exact duplicate that was removed from the top-level accepted total:

```text
Canonical kept:
- factory2-review-0011-372-412s-panel-v1-5fps track 2
- timestamps: 387.3–402.1

Duplicate kept only as audit evidence:
- factory2-review-0005-418s-panel-v1 track 1
- timestamps: 398.081–402.081
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_morning_proof_report.py tests/test_freeze_factory2_diagnostics.py tests/test_run_factory2_morning_proof.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_build_factory2_recall_work_queue.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py -q
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py scripts/freeze_factory2_diagnostics.py scripts/run_factory2_morning_proof.py scripts/diagnose_event_window.py scripts/analyze_person_panel_separation.py scripts/build_factory2_recall_work_queue.py app/services/runtime_event_counter.py app/services/person_panel_gate_promotion.py tests/test_build_morning_proof_report.py tests/test_freeze_factory2_diagnostics.py tests/test_run_factory2_morning_proof.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_build_factory2_recall_work_queue.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force --report-json data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --report-md data/reports/factory2_morning_proof_report.narrow_frozen_v2.md --run-summary-json data/reports/factory2_morning_proof_run_summary.narrow_frozen_v2.json --panel-crop-evidence-json data/reports/factory2_panel_crop_evidence.narrow_frozen_v2.json --transfer-review-packets-json data/reports/factory2_transfer_review_packets.narrow_frozen_v2.json --person-panel-separation-json data/reports/factory2_person_panel_separation.narrow_frozen_v2.json --freeze-diagnostics-dir data/diagnostics/frozen/factory2-narrow-merged-v2 --diagnostic data/diagnostics/event-windows/factory2-review-0014-000-030s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0012-145-185s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0002-222s-panel-v1/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0008-232-272s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0009-332-372s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0011-372-412s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0005-418s-panel-v1/diagnostic.json
.venv/bin/python -m scripts.build_morning_proof_report --force --output data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --markdown-output data/reports/factory2_morning_proof_report.narrow_frozen_v2.md --fp-report data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json --fp-report data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json --positive-report data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json --positive-report data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0014-000-030s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0012-145-185s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0002-222s-panel-v1/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0008-232-272s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0009-332-372s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0011-372-412s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0005-418s-panel-v1/diagnostic.json
```

Verification:

```text
52 tests passed
py_compile passed
Frozen merged proof now has a stable immutable diagnostic namespace and a deduped distinct accepted count of 12
```

Next blocker:

```text
The immutable narrow proof set is now real and beats the old broad baseline, but it is still at 12 distinct carries vs the human truth target of 23. The next bottlenecks are:
- remaining worker-overlap suppressions/uncertains inside the frozen merged set
- missing true carries outside the current accepted set
- proof/runtime still not aligned to this 12-count merged proof path
```

Exact next recommended step:

```text
Implement `scripts/export_factory2_blocked_crops.py` and `tests/test_export_factory2_blocked_crops.py`
against `data/reports/factory2_morning_proof_report.narrow_frozen_v2.json`, starting with the
remaining worker-overlap receipts in the frozen merged set.
```


## Factory2 recall recovery + crop-separation next PRD — 2026-04-28 19:16 EDT

Implemented the next bounded slice after the first proof/runtime success:

```text
AGENTS.md
CLAUDE.md
docs/PROJECT_SPEC.md
docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md
scripts/analyze_person_panel_separation.py
scripts/build_factory2_recall_work_queue.py
scripts/diagnose_event_window.py
tests/test_analyze_person_panel_separation.py
tests/test_build_factory2_recall_work_queue.py
tests/test_diagnose_event_window.py
tasks/lessons.md
```

What changed:

```text
- Increased representative receipt sampling from 3 snapshots to 9 evenly spaced observations for longer tracks, while keeping short tracks dense.
- Added receipt/gate tests proving split source-only predecessors can be merged into short source->output successors before perception gating, including multi-hop predecessor chains.
- Added a Factory2 recall work-queue builder that turns reviewed positive frame labels into cluster-level proof coverage targets.
- Wrote the next PRD: narrow-window recall recovery plus blocked crop export for panel-vs-worker separation training.
- Updated repo doctrine so the explicit target is now the human truth set of 23 carried-panel transfers with 0 false positives.
```

Real results gathered this slice:

```text
Broad resampled baseline:
- data/reports/factory2_morning_proof_report.candidate6_resampled.json
- accepted_count: 8
- suppressed_count: 41
- uncertain_count: 23

Focused narrow-window proof results already on disk:
- 0–30s: accepted_count 1
- 145–185s: accepted_count 1
- 232–272s: accepted_count 2
- 288–328s: accepted_count 1
- 332–372s: accepted_count 1
- 372–412s: accepted_count 2

Recall work queue:
- 8 reviewed positive Factory2 frames collapse into 5 likely transfer clusters
- current narrow proof windows cover all 5 reviewed-positive clusters
- the next gap is no longer obvious coverage holes; it is turning those covered windows into one immutable merged proof set that preserves the stronger narrow-window gains
```

Why this matters:

```text
The count architecture is no longer the mystery. The limiting factor is recall construction: broad mixed windows merge too much activity, while narrow windows plus denser receipts recover real carries. The next serious recall lever after window restructuring is a blocked-crop dataset for panel-vs-worker separation training on the exact worker-overlap misses.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py -q
.venv/bin/python -m py_compile scripts/diagnose_event_window.py scripts/analyze_person_panel_separation.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py
.venv/bin/python scripts/build_factory2_recall_work_queue.py --force
```

Verification:

```text
19 tests passed
representative observation sampling now preserves 9-frame evidence on long tracks
receipt refresh/gate merge logic now has coverage for split predecessor chains
```

Next blocker:

```text
The repo still does not have one clean immutable merged proof set that rolls the stronger narrow-window gains together. Shared diagnostic directories were reused during merged proof attempts, which contaminated some combined reports while sidecars were still regenerating.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/build_factory2_recall_work_queue.py --force
```

Then freeze/copy the finalized narrow diagnostic directories, build one merged proof artifact from those immutable copies, and only after that start the blocked-crop export path in `docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md`.


## Factory2 runtime/app path completion — live counting aligned with proof — 2026-04-28 14:37 EDT

Implemented the missing runtime-side commit path so Factory2 now works through the actual worker/app surface instead of only through the proof scripts:

```text
AGENTS.md
CLAUDE.md
app/services/runtime_event_counter.py
app/services/count_state_machine.py
app/workers/vision_worker.py
app/core/settings.py
app/api/routes.py
app/db/config_repo.py
app/db/event_repo.py
app/services/video_runtime.py
requirements.txt
tests/helpers.py
tests/test_runtime_event_counter.py
tests/test_count_state_machine_runtime_approval.py
tests/test_count_state_machine_adversarial.py
tests/test_settings_runtime.py
tests/test_vision_worker_states.py
tasks/lessons.md
```

What changed:

```text
- Added `RuntimeEventCounter` as the event-based runtime counter for calibrated Factory2 runs.
- The runtime counter now merges proof-grade source->output delivery evidence across split tracks and emits an explicit `approved_delivery_chain` commit instead of waiting for legacy output-settle/disappear semantics.
- `CountStateMachine` now supports idempotent proof-approved chain commits while still owning the count ledger and de-duplication.
- `VisionWorker` now routes calibrated `event_based` runs through the runtime counter, resets it correctly, and surfaces gate decisions in runtime debug artifacts.
- Settings/runtime compatibility fixes were kept in place for the live path used here, including calibrated event-based detector defaults.
- Local agent instructions now explicitly say Factory2 is not done until the actual runtime/app path counts `factory2.MOV`; proof-only success is not sufficient.
```

Real results:

```text
Proof path:
- verdict: accepted_positive_count_available
- accepted_count: 1
- suppressed_count: 11
- uncertain_count: 4
- accepted proof receipt: event0002 track 5

Live worker path on factory2.MOV (4x playback, full relevant span):
- counts_this_hour reached 1 at ~54.2s
- stayed at 1 through ~105.8s real time (~423s of video time), so the later event0006 proof window did not create an extra count

Live FastAPI/uvicorn app path:
- POST /api/control/monitor/start returned 200
- GET /api/status reached counts_this_hour: 1 at ~54.7s
- final status showed RUNNING_GREEN with counts_this_hour: 1
```

Why this matters:

```text
This closes the last real gap the user called out: Factory2 is no longer "working only in proof." The same carried-panel evidence that yields the accepted proof count now drives the actual runtime/app counter path, and the live app path was verified over HTTP instead of only through direct unit or worker harnesses.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_runtime_event_counter.py tests/test_count_state_machine_runtime_approval.py tests/test_count_state_machine.py tests/test_count_state_machine_adversarial.py tests/test_vision_worker_states.py tests/test_settings_runtime.py tests/test_api_smoke.py tests/test_dashboard_contract.py -q
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
env FC_DB_PATH=/tmp/factory2-runtime-api.db FC_LOG_DIR=/tmp/factory2-runtime-api-logs FC_DEMO_MODE=1 FC_DEMO_VIDEO_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV FC_DEMO_PLAYBACK_SPEED=4 FC_COUNTING_MODE=event_based FC_RUNTIME_CALIBRATION_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json FC_YOLO_MODEL_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt FC_PERSON_DETECT_ENABLED=1 ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
# then POST /api/control/monitor/start and poll GET /api/status until counts_this_hour becomes 1
```

Verification:

```text
55 tests passed
proof verdict: accepted_positive_count_available
proof accepted_count: 1
live worker run: count reached 1 and stayed there through the later proof window
live uvicorn/API run: counts_this_hour reached 1 through /api/status
```

Next blocker:

```text
No Factory2 blocker remains for the current definition of done. The remaining work is hardening: codify the slow live runtime/API verification into a reusable regression harness so future gate/runtime changes cannot silently reopen the proof/runtime gap.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Then add an opt-in slow regression harness that boots the app in demo mode on `factory2.MOV`, starts monitoring over HTTP, asserts `counts_this_hour == 1`, and verifies the count does not rise again across the later event window.


## PRD Success-path completion — end-to-end diagnostic regeneration + gate refresh — 2026-04-28 13:30 EDT

Implemented the final proof-path consistency work needed to make the Factory2 success path real and repeatable:

```text
app/services/person_panel_gate_promotion.py
scripts/build_morning_proof_report.py
scripts/diagnose_event_window.py
scripts/run_factory2_morning_proof.py
tests/test_person_panel_gate_promotion.py
tests/test_diagnose_event_window.py
tests/test_run_factory2_morning_proof.py
docs/superpowers/plans/2026-04-28-factory2-end-to-end-person-panel-promotion.md
```

What changed:

```text
- Extracted the person/panel sidecar interpretation + worker-overlap promotion rule into shared service code.
- Added a diagnostic refresh path that rewrites `diagnostic.json`, `track_receipts/*.json`, and hard-negative manifests from existing gate rows plus sibling `*-person-panel-separation.json` receipts.
- Fixed two refresh bugs discovered during full proof runs:
  - explicit `outside_person_ratio: 0.0` is now preserved instead of being treated as missing;
  - refresh uses the existing diagnostic gate row as the baseline instead of recomputing a new protrusion decision from receipt payloads.
- The canonical proof command now rebuilds base event-window diagnostics from their own metadata, then rebuilds transfer packets, separation receipts, refreshes gate receipts, and finally emits the proof report.
```

Real proof result now:

```text
verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
bottleneck: none
accepted receipt: event0002 track 5
accepted receipt person/panel separation: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
event0002 diagnostic allowed tracks: [5]
event0006 diagnostic allowed tracks: []
```

Why this matters:

```text
This closes the prior proof-only gap. `scripts/run_factory2_morning_proof.py --force` now regenerates the base diagnostics, recomputes the packet/separation evidence, refreshes the on-disk diagnostic receipts, and lands on the same single accepted carried-panel count. The accepted `track-000005` receipt is now promoted by `strong_person_panel_separation` with `outside_person_ratio: 0.0`, which is exactly the auditable worker-overlap case the PRD was targeting.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py tests/test_diagnose_event_window.py tests/test_person_panel_gate_promotion.py -q
python -m py_compile app/services/person_panel_gate_promotion.py scripts/diagnose_event_window.py scripts/build_morning_proof_report.py scripts/run_factory2_morning_proof.py tests/test_person_panel_gate_promotion.py tests/test_diagnose_event_window.py tests/test_run_factory2_morning_proof.py
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification:

```text
42 tests passed
proof verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
accepted track set: only event0002 track 5
```

Next blocker:

```text
Factory2 itself is no longer blocked at the PRD level; the success path is achieved. The remaining product work is beyond this PRD: generalize the same proof discipline beyond the two curated event windows and expose the accepted-count path in the broader product surface instead of only the proof/report command.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Then, if moving beyond the PRD, wire the same accepted-count receipt path into the broader counting/product entrypoint and add a held-out regression clip so future gate changes cannot reopen weak worker-overlap packets.


## PRD Milestone 4 start — proof-path gate promotion from person/panel separation — 2026-04-28 12:19 EDT

Implemented the first non-diagnostic promotion path for `factory2.MOV`:

```text
app/services/perception_gate.py
scripts/build_morning_proof_report.py
scripts/run_factory2_morning_proof.py
tests/test_perception_gate.py
tests/test_build_morning_proof_report.py
tests/test_run_factory2_morning_proof.py
```

What changed:

```text
- The perception gate now recognizes strong person/panel separation evidence as a valid override for coarse worker-body overlap, but only when the separation receipt says countable_panel_candidate and shows persistent multi-frame source/transfer evidence.
- The morning proof report now rehydrates worker-overlap gate rows from sibling `*-person-panel-separation.json` receipts and promotes only tracks that satisfy the stronger gate rule.
- The canonical proof command now auto-builds:
  - data/reports/factory2_transfer_review_packets.json
  - data/reports/factory2_person_panel_separation.json
  before rebuilding the final proof report.
- Accepted proof receipts now surface `person_panel_separation_path` directly in the decision receipt index.
```

Real proof result now:

```text
verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
bottleneck: none
accepted receipt: event0002 track 5
accepted receipt person/panel separation: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
```

Why this matters:

```text
This is the first proof run where factory2 morning evidence produces a real accepted count without lowering thresholds or counting from boxes/texture alone. The promotion is constrained to the one track whose separation receipt shows persistent silhouette-separated evidence; weaker packets remain suppressed/uncertain.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_perception_gate.py tests/test_build_morning_proof_report.py -q
.venv/bin/python -m pytest tests/test_run_factory2_morning_proof.py -q
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py -q
python -m py_compile app/services/perception_gate.py scripts/build_morning_proof_report.py scripts/run_factory2_morning_proof.py tests/test_perception_gate.py tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification:

```text
29 tests passed
proof verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
near-neighbor validation:
- event0002 track 2 → insufficient_visibility
- event0006 track 8 → insufficient_visibility
- event0006 track 6 → not_panel
```

Next blocker:

```text
The proof now cracks one carried-panel case, and nearby weaker packets did not promote, but the gate still relies on legacy stored event-window gate rows plus proof-time rehydration. The remaining product risk is end-to-end consistency: push the same separation-aware gate logic down into `scripts/diagnose_event_window.py` / live diagnostic generation so fresh diagnostics and proof replay share the same promotion path.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_perception_gate.py tests/test_run_factory2_morning_proof.py -q
```

Then move the same separation-aware promotion rule into `scripts/diagnose_event_window.py` so regenerated event-window diagnostics can produce the accepted `track 5` count without relying on proof-time rehydration.


## PRD Milestone 3 start — person/panel separation diagnostics — 2026-04-28 11:27 EDT

Implemented the next bounded perception slice after transfer packets:

```text
scripts/analyze_person_panel_separation.py
tests/test_analyze_person_panel_separation.py
```

Purpose:

```text
transfer review packet + receipt observations
→ detect the overlapping person on sampled frames
→ estimate a conservative person silhouette
→ measure mesh-like evidence in panel-box regions outside that silhouette
→ emit diagnostic-only JSON + visual receipts
```

Generated on the bounded target:

```text
data/reports/factory2_person_panel_separation.json
data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
track-000005-person-panel-separation-frame_000060.png
track-000005-person-panel-separation-frame_000081.png
track-000005-person-panel-separation-frame_000100.png
```

What the first real slice says for `event0002 track 5`:

```text
packet_id: event0002-track000005
recommendation: countable_panel_candidate
diagnostic_only: true
packet_outside_person_ratio (old bbox signal): 0.0
frame_000060 visible_nonperson_ratio: 0.542531
frame_000081 visible_nonperson_ratio: 0.319453
frame_000100 visible_nonperson_ratio: 0.226362
```

Interpretation:

```text
This is still not a count approval and did not change the gate. It is the first auditable evidence slice showing silhouette-separated mesh-like signal on the top transfer packet even when the prior coarse packet metrics said outside_person_ratio=0.0. The current output is diagnostic-only and should be treated as a candidate receipt, not a minted source token.
```

Commands run:

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/test_analyze_person_panel_separation.py -q
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py -q
python -m py_compile scripts/analyze_person_panel_separation.py tests/test_analyze_person_panel_separation.py
.venv/bin/python -m py_compile scripts/analyze_person_panel_separation.py tests/test_analyze_person_panel_separation.py
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/analyze_person_panel_separation.py --packet-id event0002-track000005 --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification / proof result:

```text
14 tests passed
proof verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
```

Next blocker:

```text
The first silhouette estimate is promising but still heuristic: YOLO person boxes + GrabCut can over-separate edges. Before any gate integration, the same diagnostic must survive on the next top packets and on negative/control cases so we know this is discrete carried-panel evidence rather than a segmentation artifact.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/analyze_person_panel_separation.py --packet-id event0006-track000001 --packet-id event0006-track000004 --force
```

Then compare those packet JSON/PNG receipts against `event0002 track 5` before touching `app/services/perception_gate.py`.

## PRD Milestone 1 start — temporal transfer review packets — 2026-04-28 10:50 EDT

Implemented first PRD-backed code slice:

```text
scripts/build_panel_transfer_review_packets.py
tests/test_build_panel_transfer_review_packets.py
```

Purpose:

```text
factory2 morning proof report / diagnostic receipts
→ re-rank worker-entangled candidates by temporal source/output evidence
→ emit transfer packet JSON/JPG artifacts for reviewer/VLM/person-panel separation work
```

Real run:

```bash
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
```

Generated:

```text
data/reports/factory2_transfer_review_packets.json
track-*-transfer-packet.json / track-*-transfer-packet.jpg beside receipt files
```

Top packet order now follows the PRD instead of outside-person ratio alone:

```text
1. event0002 track 5 — source_frames=38, output_frames=1, displacement=603.294, flow=0.501419
2. event0006 track 1 — source_frames=35, output_frames=2, displacement=456.787, flow=0.465985
3. event0006 track 4 — source_frames=33, output_frames=3, displacement=482.653, flow=0.222248
4. event0002 track 2 — source_frames=34, output_frames=0, displacement=273.665, flow=0.134594
```

Track 7 is now correctly demoted to ambiguity/control because it is single-frame/low-motion despite partial outside-person evidence.

Verification:

```bash
python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_run_factory2_morning_proof.py tests/test_analyze_panel_crop_evidence.py -q
# 10 passed
python -m py_compile scripts/build_panel_transfer_review_packets.py tests/test_build_panel_transfer_review_packets.py
.venv/bin/python -m py_compile scripts/build_panel_transfer_review_packets.py
```

Next step from PRD:

```text
Audit top transfer packets into countable_panel / not_panel / insufficient_visibility, then build person-mask/pose-aware panel separation diagnostics.
```

---

## PRD alignment — 2026-04-28 10:40 EDT

Created the active perception PRD:

```text
docs/PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md
```

`docs/PROJECT_SPEC.md` now points to this PRD as the active source of truth for the current `factory2.MOV` worker-entangled carried-panel blocker.

Next code work should follow the PRD, starting with:

```text
scripts/build_panel_transfer_review_packets.py
tests/test_build_panel_transfer_review_packets.py
data/reports/factory2_transfer_review_packets.json
```

Do not loosen the count state machine or source-token gate to force nonzero counts. The PRD keeps the doctrine: raw detections and crop texture are evidence only; the missing capability is temporal carried-panel perception plus person/panel separation.

---

## Latest manual slice — 2026-04-28 09:43:25 EDT

Commit:

```text
e40ea6f feat: add panel crop evidence probe
```

What changed:

- Added `scripts/analyze_panel_crop_evidence.py`, a bounded model-free crop texture probe for worker-entangled receipt crops. It scores raw crops for mesh-like balanced high-frequency edge texture; it is evidence only, not a count source.
- Wired the probe into `scripts/run_factory2_morning_proof.py` so the one-command proof path now also writes `data/reports/factory2_panel_crop_evidence.json` and summarizes it in `factory2_morning_proof_run_summary.json`.
- Added tests for synthetic wire-mesh vs solid worker/body crops and for proof-runner crop-evidence integration.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/reports/factory2_panel_crop_evidence.json
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
panel_crop_evidence_summary: panel_texture_candidate_receipts=4, low_panel_texture_receipts=6 among top 10 queued receipts
top queued track 7: texture_uncertain / low-confidence, not enough to allow source token
VLM spot-check of track 7 crop: too ambiguous; no clearly separable wire-mesh panel
VLM spot-check of a texture-positive crop: still ambiguous; texture may be mesh, but no distinct panel boundary
```

Interpretation:

```text
The strategy is still correct, but the last reporting-only phase is over. This slice starts attacking the real blocker: panel-vs-worker/static-stack perception. It did not produce a trusted count; it added a repeatable crop-evidence probe and showed that texture alone can surface candidates but is insufficient to approve a source token. Next useful work is person-mask/pose-aware or segmentation-assisted separation on the texture-positive receipts, not more report taxonomy.
```

Verification:

```bash
python -m pytest tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 22 passed in 0.10s

python -m py_compile scripts/analyze_panel_crop_evidence.py scripts/run_factory2_morning_proof.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py
.venv/bin/python -m py_compile scripts/analyze_panel_crop_evidence.py scripts/run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, unrelated dirty files untouched, generated report/eval artifacts left ignored/untracked.

Immediate next step:

```text
Use the four panel-texture-candidate receipts from `data/reports/factory2_panel_crop_evidence.json` as the next perception work queue. Add person-mask/pose-aware or segmentation-assisted separation to prove whether the mesh-like texture belongs to a discrete carried panel, and only then consider allowing source-token evidence.
```

## Latest cron slice — 2026-04-28 07:21:48 EDT

Commit:

```text
8aefc95 feat: summarize proof evidence gaps
```

What changed:

- Added a top-level `evidence_gap_matrix` to `scripts/build_morning_proof_report.py` so the factory2 morning report now groups every non-counted receipt by the physical proof link that failed.
- The matrix separates `panel_vs_worker_separation` from `output_entry_and_settle`, carries sample receipt paths, states why accepted count is zero, and repeats missing review asset counts.
- Markdown reports now include an `Evidence gap matrix` section before the source-token work queue.
- This is reporting only, not looser counting: raw detector detections and worker-entangled tracks still cannot count without perception-gate-approved source-token evidence.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
evidence_gap_matrix.dominant_gap: panel_vs_worker_separation
evidence_gap_matrix.evidence_links: panel_vs_worker_separation blocked 13 receipts (12 suppressed, 1 uncertain); output_entry_and_settle blocked 3 receipts (3 uncertain)
source_token_work_queue.item_count: 13
```

Interpretation:

```text
The morning bar moved closer because the report now explains the abstention in physical-evidence terms instead of merely saying every candidate was suppressed/uncertain. The current representative factory2.MOV result remains honest: 0 accepted counts. The dominant blocker is panel-vs-worker separation on worker-entangled receipts; three additional uncertain receipts need output-entry/settle evidence.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only `scripts/build_morning_proof_report.py` plus `tests/test_build_morning_proof_report.py` were committed.

Immediate next step:

```text
Attack the dominant evidence gap directly: build crop/shape/person-mask or pose-aware separation for the top `panel_vs_worker_separation` receipts, starting with the source-token work queue top item. A receipt should only become countable if it proves a discrete wire-mesh panel separate from worker body/arms/clothing and still preserves source→output/settle evidence.
```

## Latest cron slice — 2026-04-28 06:58:00 EDT

Commit:

```text
bb5d3af feat: specify source token audit evidence
```

What changed:

- Added explicit `audit_question` and `evidence_requirements_to_allow_source_token` fields to each `source_token_work_queue.top_items[]` row in `scripts/build_morning_proof_report.py`.
- Markdown proof reports now show the audit question and evidence checklist for the highest-priority worker-entangled receipts.
- This is still evidence bookkeeping, not looser counting: worker-overlap tracks remain suppressed/uncertain unless future perception evidence proves a valid active-panel source token.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
source_token_work_queue.item_count: 13
source_token_work_queue.worker_overlap_detail_counts: {'fully_entangled_with_worker': 12, 'high_overlap_partial_outside_worker': 1}
top_work_item: track 7 in factory2-event0002-98s-panel-v4-protrusion-gated, high_overlap_partial_outside_worker, receipt data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000007.json
top_audit_question: Is the partially outside-person evidence a real panel edge/sheet, or just worker limbs/clothing/background?
top_evidence_requirements: raw crops show a discrete wire-mesh/panel edge separate from worker clothing or arms; outside-person pixels are large enough and stable enough to be a physical panel, not detector jitter; source and output evidence both survive after person/part separation
```

Interpretation:

```text
The morning bar moved closer because the end-to-end report now states exactly what evidence would be required before any worker-entangled receipt can become a source token. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain. The blocker is still worker/body source-token evidence, not the count state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the top work item — track 7 from the 78–118s window — to build crop/shape/person-mask evidence that answers the report's audit question: whether the outside-person pixels are a real wire-mesh panel edge/sheet or merely worker limbs/clothing/background.
```

## Latest cron slice — 2026-04-28 06:13:44 EDT

Commit:

```text
9b64116 feat: queue source token receipt work
```

What changed:

- Added a top-level `source_token_work_queue` to `scripts/build_morning_proof_report.py` so the morning report now ranks the worker-entangled receipts that are most worth attacking next.
- The queue carries the JSON receipt, image card, raw crop paths, overlap ratios, and a recommended action per track.
- This is still evidence bookkeeping, not looser counting: raw detections and worker-overlap tracks still do not mint source tokens.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
source_token_work_queue.item_count: 13
source_token_work_queue.worker_overlap_detail_counts: {'fully_entangled_with_worker': 12, 'high_overlap_partial_outside_worker': 1}
top_work_item: track 7 in factory2-event0002-98s-panel-v4-protrusion-gated, high_overlap_partial_outside_worker, receipt data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000007.json
```

Interpretation:

```text
The morning bar moved closer because the end-to-end proof report now tells the next engineer/agent exactly which worker-entangled receipt to inspect first and which evidence layer is missing. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain. The blocker is still worker/body source-token evidence, not the count state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use `source_token_work_queue.top_items[0]` — currently track 7 from the 78–118s window — to build the next perception evidence slice: crop/shape/person-mask or pose-aware separation that can approve a true protruding/carried panel without allowing torso/arm/background motion to count.
```

## Latest cron slice — 2026-04-28 05:39:11

Commit:

```text
a9bc7eb feat: index proof decision receipts
```

What changed:

- Added a top-level `decision_receipt_index` to `scripts/build_morning_proof_report.py`, grouping every reviewed track into `accepted`, `suppressed`, and `uncertain` with direct JSON/card/raw-crop receipt paths.
- Markdown reports now include a `Decision receipt index` and sample receipt links so the morning proof is easier to audit without digging through each diagnostic file.
- This is bookkeeping, not looser counting: raw detector outputs still cannot count; only perception-gate-approved source tokens enter the accepted bucket.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
proof_readiness.status: detector_seed_passes_but_worker_overlap_blocks_source_tokens
decision_receipt_index.counts: {'accepted': 0, 'suppressed': 12, 'uncertain': 4}
missing_review_asset_counts: {}
first_suppressed_receipt: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000001.json
```

Interpretation:

```text
The morning bar moved closer because the end-to-end report now has an auditable decision index: every suppressed/uncertain track points to the receipt assets proving why it did not count. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain, with worker/body overlap still the blocker.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the indexed suppressed/uncertain receipt list as the work queue for the worker-entangled tracks, then add crop/shape/person-mask or pose-aware evidence that can approve true carried/protruding panels without opening the door to torso/arm/background counts.
```

## Latest cron slice — 2026-04-28 05:03:09 EDT

Commit:

```text
5dd72e3 feat: classify proof readiness
```

What changed:

- Added `proof_readiness` to `scripts/build_morning_proof_report.py`, so the morning artifact now says whether the current blocker is detector safety, positive recall, or source-token gate evidence.
- The readiness classifier preserves the count doctrine: raw detector outputs still do not count; they only help determine whether the detector is good enough and whether the bottleneck has moved to worker/body source-token evidence.
- Markdown reports now include a `Proof readiness` section with status, dominant failure link, detector pass/fail flags, and next action.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
proof_readiness.status: detector_seed_passes_but_worker_overlap_blocks_source_tokens
proof_readiness.dominant_failure_link: worker_body_overlap
selected detector: models/panel_in_transit.pt at confidence 0.25
selected detector positive pass: true, recall 1.0
selected detector hard-negative FP: 0 detections
safe detector candidates: 4
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
worker_overlap_detail_counts: fully_entangled_with_worker=12, high_overlap_partial_outside_worker=1
```

Interpretation:

```text
The morning bar moved closer because the report now distinguishes “the detector seed evidence is currently good enough on reviewed positives/hard negatives” from “the representative factory event count still abstains.” The blocker is now stated cleanly: worker-entangled source-token evidence, not hard-negative detector false positives or reviewed-positive recall.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Build the crop/shape/person-mask or pose-aware evidence layer for the 12 fully-entangled worker-overlap tracks so the system can approve true carried/protruding panels while continuing to suppress torso/arm/background motion.
```

## Latest cron slice — 2026-04-28 04:28:40 EDT

Commit:

```text
77942a6 feat: select detector in proof report
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so the end-to-end proof report now chooses an advisory detector/model threshold from paired hard-negative and positive eval reports.
- Selection rule is intentionally conservative: zero hard-negative false positives first, then highest positive-label recall. This does **not** allow raw detector detections to count; it only identifies the safest currently evaluated perception candidate.
- The JSON report now includes `detector_selection` with all candidates, safe-candidate count, report paths, positive recall, and hard-negative FP evidence.
- The Markdown morning report now has a `Detector selection` section so the morning artifact says which detector is best and why.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
safe detector candidates: 4 / 4
selected detector: models/panel_in_transit.pt at confidence 0.25
selected detector positive recall: 8 / 8 labels matched, recall 1.0
selected detector hard-negative FP: 0 detections on 16 hard-negative images
```

Interpretation:

```text
The morning bar moved closer on the model/eval side: the report no longer just dumps multiple eval files; it explicitly picks the best currently safe detector threshold while preserving the abstention on representative event counts. The remaining blocker is still source-token perception evidence under worker/body overlap, not detector hard-negative FP on the exported crops.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the selected safe detector as the baseline, then add crop/shape/person-mask or pose-aware evidence for the fully-entangled worker-overlap tracks so true carried/protruding mesh panels can mint source tokens while torso/arm/background tracks remain suppressed.
```

## Latest cron slice — 2026-04-28 03:53:52 EDT

Commit:

```text
43ef0af feat: detail worker overlap proof failures
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so worker/body-overlap failures are no longer one blunt bucket.
- Added `worker_overlap_detail_counts` at report and per-window level, with per-track `worker_overlap_detail` on each decision receipt.
- New detail buckets distinguish `fully_entangled_with_worker`, `high_overlap_partial_outside_worker`, `protrusion_candidate_not_approved`, and `allowed_by_protrusion`.
- This keeps the source-token doctrine intact: the report explains why tracks were suppressed/uncertain without letting raw detections increment counts.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
worker_overlap_detail_counts: fully_entangled_with_worker=12, high_overlap_partial_outside_worker=1
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The abstention is now more precise: nearly every worker-overlap failure is fully entangled with the worker/person box rather than a clean protruding-panel candidate. The next useful perception slice is not loosening the gate; it is better crop/shape/person-mask evidence that can prove a panel exists outside the worker silhouette before minting source tokens.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Add crop/shape/person-mask or pose-aware evidence for the 12 fully-entangled worker-overlap tracks so the system can separate true carried/protruding mesh panels from torso/arm/background motion before source-token creation.
```

## Latest cron slice — 2026-04-28 03:19:29 EDT

Commit:

```text
d167993 feat: classify proof report failure links
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so the morning report now classifies each diagnostic track into a physical evidence failure link, not just a raw gate reason.
- Added `failure_link_counts` at report and per-window level, with categories such as `worker_body_overlap`, `missing_output_settle`, `static_stack_or_resident_output`, and `insufficient_active_panel_evidence`.
- Added `track_decision_receipts[]` entries that connect each track decision to its JSON receipt, image card, raw crop paths, gate reason, flags, and evidence summary.
- This keeps count logic conservative: no raw detector or diagnostic row can increment counts without a perception-gate-approved source token.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The morning proof now says exactly why it abstained: most rejected/uncertain tracks still fail because the candidate box is too entangled with worker/body evidence, with the remaining failures lacking output-settle evidence. The current weak link is still perception evidence/gating, not the source-token state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 18 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Improve the perception evidence feeding `worker_body_overlap`: add crop/shape/person-correlation scoring for track receipts so the gate can separate true protruding panels from torso/arm/background motion before creating source tokens.
```

## Latest cron slice — 2026-04-28 02:44:27 EDT

Commit:

```text
45e2d9d feat: add factory2 proof runner
```

What changed:

- Added `scripts/run_factory2_morning_proof.py`, a one-command runner for the representative `factory2.MOV` proof path.
- The runner reruns detector false-positive eval and detector positive eval across available models and confidence thresholds, then rebuilds the accepted/suppressed/uncertain morning proof report from diagnostic receipts.
- It writes `data/reports/factory2_morning_proof_run_summary.json` alongside the existing JSON/Markdown proof report.
- It explicitly keeps raw detector outputs as eval evidence only; counts still require perception-gate-approved source-token receipts.

One-command rerun path:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Real artifacts from this run:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf010.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf010_iou030.json
```

Real runner result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
models evaluated: panel_in_transit.pt, caleb_metal_panel.pt
confidence thresholds: 0.25, 0.10
```

Verification:

```bash
python -m pytest tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 18 passed in 0.04s

python -m py_compile scripts/run_factory2_morning_proof.py tests/test_run_factory2_morning_proof.py
.venv/bin/python -m py_compile scripts/run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no training run, no sensitive files read/staged, generated reports/eval artifacts left ignored/untracked, and only the new proof runner plus tests were committed.

Immediate next step:

```text
Now that the proof path is one command, improve the actual perception bottleneck: add crop-level/track-level evidence for worker-overlap cases so the gate can distinguish a real protruding carried panel from torso/arm/background motion before minting source tokens.
```

## Latest cron slice — 2026-04-28 02:09:50 EDT

Commit:

```text
c328fec feat: add detector positive eval to proof report
```

What changed:

- Added `scripts/eval_detector_positives.py`, a positive-side active-panel detector eval harness for reviewed YOLO positives.
- It loads positives from the assembled dataset manifest or non-empty YOLO labels, runs detector inference, matches detections to labels by IoU, and writes receipt JSON with label recall, matched/missed labels, per-image detections, and no-overwrite protection.
- Updated `scripts/build_morning_proof_report.py` so the morning report includes positive detector eval alongside hard-negative false-positive eval.
- Fixed the morning report FP summarizer to read the nested `summary` shape emitted by the FP harness.

Real artifacts from this run:

```text
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf010_iou030.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Positive detector eval result on the assembled `active_panel` positives:

```text
panel_in_transit.pt @ conf 0.25, IoU 0.30: 8 / 8 labels matched, recall 1.0
panel_in_transit.pt @ conf 0.10, IoU 0.30: 8 / 8 labels matched, recall 1.0
caleb_metal_panel.pt @ conf 0.25, IoU 0.30: 0 / 8 labels matched, recall 0.0
caleb_metal_panel.pt @ conf 0.10, IoU 0.30: 0 / 8 labels matched, recall 0.0
```

Updated combined morning report result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The representative event-count answer is still accepted_count=0 because no source-token track survived the perception gate. The detector-side picture is now clearer: panel_in_transit.pt sees the 8 reviewed positives and stays clean on staged hard negatives; caleb_metal_panel.pt should not be used for this active_panel proof because it misses all reviewed positives in this dataset.
```

Verification:

```bash
python -m pytest tests/test_eval_detector_positives.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_diagnose_event_window.py tests/test_run_clip_eval.py tests/test_perception_gate.py -q
# 32 passed in 0.08s

python -m py_compile scripts/eval_detector_positives.py scripts/build_morning_proof_report.py tests/test_eval_detector_positives.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/eval_detector_positives.py scripts/build_morning_proof_report.py
git diff --check
```

Scope guard held: no cron changes, no sensitive files read/staged, generated eval/report artifacts left untracked/ignored, and only relevant source/test files were committed.

Immediate next step:

```text
Keep panel_in_transit.pt as the current proof-path detector candidate. The next useful slice is not more model comparison; it is crop-level/track-level evidence for worker-overlap cases, so the perception gate can distinguish a real protruding carried panel from torso/arm/background motion before minting source tokens.
```

## Latest cron slice — 2026-04-28 01:48:35 EDT

Commit:

```text
94020da feat: add morning proof report builder
```

What changed:

- Added `scripts/build_morning_proof_report.py`, a bounded end-to-end proof/report aggregator for the morning bar.
- It combines existing `factory2.MOV` diagnostic receipts, perception-gate decisions, hard-negative manifests, overlay paths, and detector false-positive eval reports.
- It explicitly reports `accepted_count`, `suppressed_count`, `uncertain_count`, bottleneck, receipt paths, and detector FP totals without promoting raw unaudited detections into counts.
- Added `tests/test_build_morning_proof_report.py` covering accepted/suppressed/uncertain separation, allowed source tokens, markdown receipt output, and CLI writes.

Real artifacts from this run:

```text
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf010.json
```

Report result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
total_tracks_reviewed: 16
bottleneck: perception_gate_worker_body_overlap
```

Detector FP widening result:

```text
panel_in_transit.pt @ conf 0.25: 0 / 16 hard-negative images with false positives
panel_in_transit.pt @ conf 0.10: 0 / 16 hard-negative images with false positives
caleb_metal_panel.pt @ conf 0.25: 0 / 16 hard-negative images with false positives
caleb_metal_panel.pt @ conf 0.10: 0 / 16 hard-negative images with false positives
combined report: 0 false-positive detections across 64 hard-negative eval rows
```

Representative diagnostic evidence included in report:

```text
factory2-event0002-98s-panel-v4-protrusion-gated: accepted 0, suppressed 5, uncertain 3; reasons worker_body_overlap=5, source_without_output_settle=3
factory2-event0006-370s-panel-v4-protrusion-gated: accepted 0, suppressed 7, uncertain 1; reasons worker_body_overlap=7, source_without_output_settle=1
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_diagnose_event_window.py tests/test_run_clip_eval.py tests/test_perception_gate.py -q
# 26 passed in 0.07s

python -m py_compile scripts/build_morning_proof_report.py scripts/eval_detector_false_positives.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py scripts/eval_detector_false_positives.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated eval/report artifacts left untracked/ignored, and only the new source/test files were committed.

Immediate next step:

```text
Use the report as the current morning proof artifact. The clean hard-negative FP result says the current models are not firing on staged negatives, but the diagnostics still abstain because source-to-output-looking tracks overlap worker body or lack output settle evidence. Next code slice should add positive-side detector eval/recall on the 8 reviewed positives and/or stronger crop-level panel evidence for worker-overlap cases before trusting any new source token.
```

## Latest cron slice — 2026-04-28 01:27:49 EDT

Commit:

```text
4ae767f feat: add detector false-positive eval harness
```

What changed:

- Added `scripts/eval_detector_false_positives.py`, a lightweight pre-training detector FP harness for hard-negative images.
- It accepts the assembled dataset `data.yaml` or `dataset_manifest.json`, evaluates only `hard_negative` / empty-label images, and writes a receipt-style JSON report.
- It keeps YOLO/Ultralytics loading inside the runtime path, so tests remain injectable and base-Python compatible.
- Added tests for dataset-manifest loading, empty-label fallback scanning, receipt writing, confidence filtering, and no-overwrite behavior.

Real artifact from this run:

```text
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json
```

Real result on the assembled hard negatives:

```text
model: models/panel_in_transit.pt
confidence: 0.25
hard_negative_images: 16
images_with_false_positives: 0
false_positive_detections: 0
false_positive_image_rate: 0.0
```

Verification:

```bash
python -m pytest tests/test_eval_detector_false_positives.py tests/test_assemble_active_panel_dataset.py tests/test_export_hard_negatives.py -q
# 14 passed in 0.02s

python -m py_compile scripts/eval_detector_false_positives.py scripts/assemble_active_panel_dataset.py tests/test_eval_detector_false_positives.py
.venv/bin/python -m py_compile scripts/eval_detector_false_positives.py

.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/panel_in_transit.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json \
  --confidence 0.25 \
  --force
```

Scope guard held: no training run, no cron changes, no sensitive files read/staged, and only the new source/test files were committed.


## Current goal

Keep pushing the Factory Output Vision MVP toward reliable source→output counting on representative `factory2.MOV` footage.

Core doctrine:

```text
detections are observations, not counts
only perception-gate-approved source-token tracks can reach CountStateMachine
output-only/static-stack/worker-body tracks must not count
all counts/suppressions need receipts
AI/VLM audit is reviewer/gate, not the counter itself
```

## Latest committed work

Latest commit:

```text
2277eba feat: assemble active panel dataset with hard negatives
602c457 feat: allow protruding panel source tokens
```

Changed files:

```text
scripts/assemble_active_panel_dataset.py
tests/test_assemble_active_panel_dataset.py
```

What changed:

- Added a dataset assembly bridge from AI-reviewed positives + hard-negative exports into YOLO trainable layout.
- Positives must come from `label-quality-reviewed-v1` `trainable_labels`.
- Hard negatives come from `factory-hard-negative-export-v1` and are copied with empty YOLO label files.
- Writes `data.yaml` and `dataset_manifest.json` so the next training/eval step has a real SSoT.
- Refuses negative-only datasets unless `--allow-negative-only` is explicitly passed.

Real smoke output:

```text
data/labels/active_panel_dataset_with_hard_negatives_v1/dataset_manifest.json
positive_count: 8
hard_negative_count: 16
total_images: 24
empty_negative_labels: 16
images/train: 24
labels/train: 24
```

Previous commit from cron:

```text
602c457 feat: allow protruding panel source tokens
```

## Verification from latest run

Focused tests, compile, and real dataset assembly smoke:

```bash
python -m pytest tests/test_assemble_active_panel_dataset.py tests/test_export_hard_negatives.py tests/test_train_custom_model_label_gate.py tests/test_review_labels_ai.py -q
python -m py_compile scripts/assemble_active_panel_dataset.py scripts/export_hard_negatives.py train_custom_model.py
python scripts/assemble_active_panel_dataset.py \
  --reviewed-label-manifest data/labels/active_panel_reviewed_autopilot-v1_minconf050.json \
  --hard-negative-export data/labels/hard_negatives/factory2-v3-person-gated/hard_negative_export.json \
  --out-dir data/labels/active_panel_dataset_with_hard_negatives_v1 \
  --force
```

Result:

```text
17 passed in 0.02s
py_compile passed
real smoke assembled 24-image YOLO dataset: 8 positives + 16 empty-label hard negatives
```

## Recent prior work still relevant

Recent commits before this run:

```text
a2c482d feat: export raw hard-negative crops
21b0c03 feat: export hard negatives for review
bab09f6 feat: export diagnostic hard negatives
ce58be6 fix: keep diagnostic receipts python39 compatible
33f9cae feat: add diagnostic track image receipts
```

The diagnostic loop now emits JSON receipts, JPG receipt cards, raw crop assets, and hard-negative manifests/exports. Use those artifacts to mine failure cases rather than forcing ambiguous raw counts.

## Tool-cap / handoff reliability rule

The 00:44 manual continuation hit the tool-call cap after committing `a2c482d` and before updating this handoff. The fix is procedural and now also baked into the cron prompt:

```text
1. update HANDOFF.md at start with IN PROGRESS
2. make exactly one small commit-sized change
3. after commit, update HANDOFF.md immediately
4. only then do optional extra work
```

Hard rule for future runs: if meaningful code changed or a commit was created, HANDOFF.md gets updated before any further implementation. Stale handoff is worse than incomplete work.

## Current dirty/untracked files to avoid

Known unrelated or sensitive files remain dirty/untracked. Do not inspect, stage, or commit unless Thomas explicitly asks:

```text
M .env.example
M CLAUDE.md
M frontend/.env.example
M frontend/package-lock.json
?? .claude/
?? .infisical.json
?? AGENTS.md
?? datasets/test-3/
?? frames/
?? models/caleb_metal_panel.pt
?? runs/
?? scripts/backend-with-infisical.sh
```

`.hermes/HANDOFF.md` is maintained by the cron loop and may appear under `?? .hermes/` if the folder is not tracked. Do not stage `.hermes/overnight.lock`.

Never read or quote `.infisical.json`, `.env`, credentials, tokens, or connection-string-bearing files.

## Latest generated diagnostics

Most recent known representative `factory2.MOV` v3 person-gated diagnostics from prior run:

```text
factory2-event0002-98s-panel-v3-person-gated: 8 JSON receipts, 8 JPG cards, 8 hard negatives, 12 raw crops, allowed source-token tracks 0
factory2-event0006-370s-panel-v3-person-gated: 8 JSON receipts, 8 JPG cards, 8 hard negatives, 14 raw crops, allowed source-token tracks 0
data/labels/hard_negatives/factory2-v3-person-gated/hard_negative_export.json: 16 exported negatives, review_only=false: 16
```

The current commit changes the gate policy but did not rerun real diagnostics. Next run should test whether any existing representative candidate now qualifies via protrusion, and audit any allowed receipt visually before trusting it.


## Manual v4 protrusion smoke — 2026-04-28 01:02:06

Ran both representative `factory2.MOV` v4 protrusion-gated diagnostic windows after `602c457`.

Results:

```text
factory2-event0002-98s-panel-v4-protrusion-gated:
  diagnostic candidates: 1
  gate allow_source_token: 0
  gate reject/uncertain: 5 / 3
  receipts/cards/raw crops/hard negatives: 8 / 8 / 12 / 8

factory2-event0006-370s-panel-v4-protrusion-gated:
  diagnostic candidates: 2
  gate allow_source_token: 0
  gate reject/uncertain: 7 / 1
  receipts/cards/raw crops/hard negatives: 8 / 8 / 14 / 8
```

No VLM audit was needed because there were no newly allowed source-token receipt cards. The protrusion-aware gate remains conservative on these two windows.

Immediate implication: next code slice should not loosen the count state machine. Improve the perception features feeding the gate: raw-crop shape/edge/protrusion evidence, motion/person correlation, or a person-mask/pose-aware protrusion score.


## PRD/roadmap alignment — 2026-04-28 01:22:28 EDT

Updated product docs so the overnight loop has an explicit target and definition of done:

```text
docs/PROJECT_SPEC.md
docs/ROADMAP.md
```

Clarified:

- representative `factory2.MOV` source→output proof is the current target;
- detections are observations, not counts;
- source-token delivery is the count rule;
- output-only/static-stack/resident/repositioned/worker-body ambiguity must not count;
- success requires receipts/evidence artifacts, not unaudited raw counts;
- tonight is done when the pipeline can mine/evaluate/gate/export hard negatives/assemble dataset and add detector FP eval prep with handoff continuity.


## Morning "make it work" target — 2026-04-28 01:43:22 EDT

Thomas clarified the bar: by morning he wants to see this working, with docs updated.

Operational interpretation for cron/manual runs:

```text
factory2.MOV
→ candidate event windows
→ diagnostic receipts/overlays/raw crops
→ perception-gated source-token counting
→ detector/model eval on positives + hard negatives
→ accepted_count / suppressed / uncertain report with receipts
```

Morning success is not a pile of utilities. It is at least one end-to-end representative eval/report path that runs without manual intervention and clearly separates:

- trusted accepted counts;
- suppressed resident/static-stack/reposition/worker-body candidates;
- uncertain candidates with evidence-failure reasons.

Docs updated accordingly:

```text
docs/PROJECT_SPEC.md section 1.3
/docs/ROADMAP.md v1.0 success metric
```

Next slices should bias toward end-to-end proof/reporting over further isolated helpers. If a trusted positive cannot be produced from `factory2.MOV`, produce an auditable failure report with receipt paths and the exact bottleneck. Do not claim raw unaudited counts work.


## Stronger morning definition — 2026-04-28 01:46:38 EDT

Thomas clarified: by morning this should not merely have a better loop; it should work and work well.

Definition now written into `docs/PROJECT_SPEC.md` section 1.3:

Works:

- one command or documented command sequence runs the representative `factory2.MOV` proof path without manual intervention;
- output report separates `accepted_count`, `suppressed`, and `uncertain` events;
- every event links to receipts: JSON, image card/overlay, and relevant crop/frame evidence;
- raw detector detections cannot directly increment counts;
- output-only/resident/reposition/static-stack/worker-body tracks are suppressed or marked uncertain with reasons.

Works well:

- known hard-negative `factory2.MOV` windows have audited false positive counts of zero;
- detector FP behavior is measured across exported hard negatives at multiple confidence thresholds;
- positive/active-panel behavior is measured separately from hard-negative suppression;
- any candidate/trained model must beat or match current model on hard negatives before clip eval;
- final morning report says which clips/windows passed, failed, and why;
- docs and handoff contain the exact rerun command path.

Not acceptable by morning:

- unaudited raw counts;
- metrics without event receipts;
- crop piles without count/suppress report;
- suppressing everything without explaining whether the detector missed the panel or the gate rejected it;
- loosening count logic to make numbers look better.

## Immediate next step

The lightweight hard-negative FP harness now exists and `panel_in_transit.pt` produced zero detections on the current 16 hard negatives at confidence 0.25. Next cron slice should widen the detector eval before training:

```text
run FP eval at lower confidence, e.g. 0.10 / 0.15
→ compare panel_in_transit.pt against any available customer model such as caleb_metal_panel.pt without committing model artifacts
→ if FP remains clean, run a small bounded active_panel training/eval dry run from data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml
→ evaluate positives and hard negatives separately before using any new .pt in clip eval
```

Example commands:

```bash
.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/panel_in_transit.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json \
  --confidence 0.10 \
  --force

.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/caleb_metal_panel.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json \
  --confidence 0.25 \
  --force
```

Parallel next perception improvement remains: add stronger raw-crop-based panel-evidence features for the gate. The v4 smoke allowed zero source-token tracks, so do not loosen the count state machine.

```bash
.venv/bin/python scripts/diagnose_event_window.py \
  --video data/videos/from-pc/factory2.MOV \
  --calibration data/calibration/factory2_ai_only_v1_no_gate.json \
  --out-dir data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated \
  --start 78 --end 118 --fps 3 \
  --model models/panel_in_transit.pt \
  --person-model yolo11n.pt \
  --confidence 0.15 \
  --tracker-match-distance 280 \
  --force

.venv/bin/python scripts/diagnose_event_window.py \
  --video data/videos/from-pc/factory2.MOV \
  --calibration data/calibration/factory2_ai_only_v1_no_gate.json \
  --out-dir data/diagnostics/event-windows/factory2-event0006-370s-panel-v4-protrusion-gated \
  --start 350 --end 390 --fps 3 \
  --model models/panel_in_transit.pt \
  --person-model yolo11n.pt \
  --confidence 0.15 \
  --tracker-match-distance 280 \
  --force
```

Then inspect `perception_gate_summary` and VLM-audit any newly allowed source-token receipt cards. If none are allowed, the next code slice should add a stronger protrusion/shape feature from raw crops rather than only bbox outside-person ratio.

## Overnight cron loop protocol

A fresh Hermes cron run should treat this file as the source of truth. It should do one bounded, commit-sized slice, then update this handoff before exiting.

Loop contract:

1. Acquire a local lock so two runs do not edit the repo at once:

```bash
mkdir -p .hermes
if ! mkdir .hermes/overnight.lock 2>/dev/null; then
  echo "Another overnight Factory Vision run is active; exit cleanly."
  exit 0
fi
trap 'rmdir .hermes/overnight.lock' EXIT
```

2. Read current state:

```bash
git status --short
git log --oneline -5
cat .hermes/HANDOFF.md
```

3. Continue only the next highest-leverage Factory Vision slice.

4. Stage/commit only intentional Factory Vision source/test/handoff files. Do not stage unrelated dirty files or secrets.

5. Run focused tests and relevant regression tests before committing.

6. Update this handoff with:

```text
latest commit hash
what changed
verification output
remaining dirty/untracked files to avoid
exact next step for next cron run
```

7. Final response should be concise with commit hash, tests, and next step.

Hard stop rules:

- Never read `.infisical.json`, `.env`, or secret-bearing files.
- Never stage unrelated dirty/untracked files.
- If repo state contradicts this handoff, stop after writing the contradiction into `.hermes/HANDOFF.md` and report it.
- If tests fail, fix if obvious; otherwise leave a clear failure section in this handoff and report.
- Do not create more cron jobs from inside cron.

---

## 2026-04-28 Oracle Strategy Reset — Factory2 Human-Countable Gap

Oracle was asked for a hard reset on why a human can count `factory2.MOV` while the pipeline still abstains.

Conclusion:
- Count/audit architecture is right: source tokens, suppression, receipts, hard negatives, one-command proof should stay.
- Perception abstraction is wrong/incomplete: detector boxes + coarse person-box overlap + crop texture do not match how humans count.
- Missing capability: amodal carried-panel tracking with person/panel separation over time. Humans use temporal continuity, hand-object relationship, source/output context, and object permanence.
- Do not loosen gates or count from texture/detections.

Oracle recommended immediate next slice:
1. Build temporal transfer review packets for strongest worker-entangled source→output candidates.
2. Re-rank candidates by source/output continuity, source/output frame counts, displacement, flow coherence, and non-static evidence — not outside-person ratio alone.
3. Prioritize long tracks like event0002 track 5, event0006 tracks 1/4, event0002 track 2; treat track 7 as ambiguity/control, not primary unlock.
4. Then add person-mask/pose-aware panel separation.
5. Train only a narrow active-carried-panel model after labels exist, with masks/labels for visible active carried panel separable from worker/static stack.

Stop doing:
- More report taxonomy.
- Bbox threshold fiddling as the main solve.
- Crop texture as approval evidence.
- Lowering confidence/gates to force nonzero counts.
- Treating single-frame detections as high-value count candidates.

Immediate implementation target:
`scripts/build_panel_transfer_review_packets.py` plus tests, emitting `data/reports/factory2_transfer_review_packets.json` and per-track temporal packet artifacts.

---

## 2026-04-28 Crop Classifier Promotion And Runtime Reality

What changed in the working tree:
- Added the track-label application helper:
  - `scripts/apply_factory2_track_review_labels.py`
  - `tests/test_apply_factory2_track_review_labels.py`
- Added worker-reference negative export:
  - `scripts/export_factory2_worker_reference_crops.py`
  - `tests/test_export_factory2_worker_reference_crops.py`
- Extended `scripts/build_factory2_crop_training_dataset.py` so it can build binary `carried_panel|worker_only` datasets and emit a classification-friendly directory layout.
- Added the second-stage crop classifier service:
  - `app/services/person_panel_crop_classifier.py`
  - `tests/test_person_panel_crop_classifier.py`
- Wired crop-classifier evidence into:
  - `app/services/perception_gate.py`
  - `app/services/person_panel_gate_promotion.py`
  - `scripts/diagnose_event_window.py`
  - `app/services/runtime_event_counter.py`
- Copied trained weights to:
  - `models/factory2_person_panel_binary_manual_v1.pt`

What was verified:
- Binary crop dataset report:
  - `data/reports/factory2_crop_training_dataset.binary_manual_v1.json`
  - `ready_for_training: true`
  - label counts: `carried_panel: 218`, `worker_only: 41`
- Trained classifier weights from the binary dataset and promoted the best checkpoint into `models/`.
- Focused test suite:
  - `80 passed`
  - command:
    ```bash
    .venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_diagnose_event_window.py tests/test_build_morning_proof_report.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py tests/test_perception_gate.py tests/test_person_panel_crop_classifier.py tests/test_build_factory2_crop_training_dataset.py tests/test_apply_factory2_track_review_labels.py tests/test_export_factory2_worker_reference_crops.py -q
    ```
- Refreshed frozen narrow proof via direct freeze/refresh/report rebuild:
  - `data/reports/factory2_morning_proof_report.narrow_frozen_v2.json`
  - `accepted_count: 15`
  - `suppressed_count: 2`
  - `uncertain_count: 32`
  - `reason_counts: moving_panel_candidate=19, source_without_output_settle=32, static_stack_edge=2`
- Important runtime verification lesson:
  - demo-mode uvicorn/app runs are looped forever because `app/services/frame_reader.py` uses `ffmpeg -stream_loop -1`
  - long-running `counts_this_hour` values in demo mode are not one-pass truth
- No-loop single-pass runtime harness result on `factory2.MOV` after crop-classifier promotion:
  - `final_count: 17`
  - event timestamps included:
    - `5.5, 23.6, 60.5, 78.6, 110.9, 129.9, 147.0, 184.2, 210.4, 233.0, 252.0, 286.4, 303.5, 347.1, 367.2, 384.3, 422.6`

What this means:
- The perception blocker materially moved.
- Proof moved from the old `12` floor to `15`.
- One-pass runtime moved from the old single-count story to `17`, but that is still below the human truth target of `23`.
- The dominant remaining blocker is now source→output chain recall across split tracks, not person/panel separation alone.

Additional tool now built:
- `scripts/audit_factory2_runtime_events.py`
- `tests/test_audit_factory2_runtime_events.py`

Exact next step:
1. Run `scripts/audit_factory2_runtime_events.py` on the full file and on late-window slices, save the JSON ledger under `data/reports/`.
2. Diff the `17` one-pass runtime events against the human `23` truth set and identify the six missing deliveries.
3. Then fix runtime/source-chain recall with bounded chain-link logic; do not loosen perception thresholds.

---

## 2026-04-28 Runtime Recall Audit And Chain Deduping

What changed:
- Added a runtime truth-gap analyzer:
  - `scripts/analyze_factory2_runtime_truth_gap.py`
  - `tests/test_analyze_factory2_runtime_truth_gap.py`
- Added a truth-candidate reconstruction ledger builder:
  - `scripts/reconstruct_factory2_truth_candidates.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
- Extended runtime predecessor stitching in `app/services/runtime_event_counter.py` so gate-side split-chain linking survives for the same lifetime as source tokens instead of dying after a short fixed gap.
- Fixed `app/services/count_state_machine.py` so `approved_delivery_chain` no longer double-counts overlapping output residents, while still allowing later real deliveries into the same output area after a bounded recent-resident window.
- Added new regression coverage in:
  - `tests/test_runtime_event_counter.py`
  - `tests/test_count_state_machine.py`

What was verified:
- New targeted suites passed:
  - `tests/test_analyze_factory2_runtime_truth_gap.py`: `3 passed`
  - `tests/test_reconstruct_factory2_truth_candidates.py`: `3 passed`
- Runtime/state-machine regression suites passed after the chain and dedupe fixes:
  - `tests/test_count_state_machine.py tests/test_runtime_event_counter.py`: `26 passed`
- Broader affected verification passed:
  - `63 passed`
  - command:
    ```bash
    .venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py tests/test_analyze_factory2_runtime_truth_gap.py tests/test_reconstruct_factory2_truth_candidates.py tests/test_perception_gate.py tests/test_person_panel_gate_promotion.py tests/test_diagnose_event_window.py -q
    ```
- Narrow runtime canary on `140–190s` with the final runtime logic:
  - `data/reports/factory2_runtime_event_audit.140_190.gap45_recentdedupe.json`
  - `final_count: 2`
  - surviving events:
    - `146.971`
    - `184.272`
- That canary matters because an intermediate runtime patch temporarily produced a bad duplicate near `184.372`, and the final recent-resident dedupe removed it without deleting the legitimate later carry.

What Oracle clarified:
- The repo evidence supports that the human target is `23`, but it does **not** appear to contain a single authoritative checked-in 23-event timestamp ledger.
- `data/reports/factory2_track_labels.manual_v1.json` is crop/track carried-panel evidence, not the full event-truth ledger.
- The defensible reconstruction path is:
  - proof-confirmed accepted receipts
  - no-loop runtime event audit JSON
  - manual crop-visible track evidence as secondary prioritization only

Current blocker:
- Full-file post-fix runtime audit is still the gating measurement:
  - target output path:
    - `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json`
- Until that completes, do not claim a new full `factory2.MOV` one-pass count.
- After the earlier runtime bugs were fixed, the remaining task is to see the real full-file count on the corrected runtime and then continue eliminating the residual misses toward `23`.

Exact next step:
1. Wait for `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json` to finish writing and record its `final_count`.
2. Run `scripts/reconstruct_factory2_truth_candidates.py` against that audit output to produce a concrete reconciliation ledger.
3. Use the runtime-only reconciliation rows to identify the next missing delivery class, then patch chain recall again without loosening perception gates.

---

## 2026-04-28 Proof Alignment Search To 23

What changed:
- Added proof-alignment helpers:
  - `scripts/build_factory2_proof_alignment_queue.py`
  - `scripts/build_factory2_runtime_backed_proof_set.py`
  - `scripts/optimize_factory2_proof_set.py`
- Added tests:
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
- Saved the execution plan at:
  - `docs/superpowers/plans/2026-04-28-factory2-proof-alignment-to-23.md`
- Built new focused diagnostics for the uncovered runtime-only proof gaps:
  - `factory2-review-0015-000-016s-panel-v1-5fps`
  - `factory2-review-0016-274-294s-panel-v1-5fps`
  - `factory2-review-0017-298-314s-panel-v1-5fps`
  - `factory2-review-0018-414-427s-panel-v1-5fps`
  - `factory2-review-0019-000-010s-panel-v1-8fps`
  - `factory2-review-0020-304-309s-panel-v1-8fps`
  - `factory2-review-0021-423-427s-panel-v1-8fps`
  - `factory2-review-0022-302-307s-panel-v1-8fps`
  - `factory2-review-0023-421-427s-panel-v1-8fps`

What was verified:
- New proof-set helper suites passed:
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `7 passed`
- `tests/test_diagnose_event_window.py` still passed after the focused diagnostic work:
  - result: `14 passed`
- The optimizer found the strongest existing proof set from the current diagnostic pool:
  - artifact: `data/reports/factory2_optimized_proof_set.runtime23_live_narrow_v1.json`
  - best existing-window result:
    - `accepted_count: 19`
    - `covered_runtime_events: 19`
    - selected added diagnostics:
      - `factory2-review-0000-000-078s-panel-v2-5fps`
      - `factory2-review-0006-058-099s-panel-v1-5fps`
      - `factory2-review-0007-112-152s-panel-v1-5fps`
      - `factory2-review-0005-396-427s-panel-v2`
- Focused proof-gap results:
  - `factory2-review-0016-274-294s-panel-v1-5fps` recovered the missing `286.408s` runtime event as an accepted proof carry.
  - `factory2-review-0019-000-010s-panel-v1-8fps` recovered the missing opener at `5.5s` as an accepted proof carry ending exactly at `5.5`.
  - combined proof artifact:
    - `data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json`
    - `accepted_count: 21`
    - remaining uncovered runtime timestamps:
      - `305.708`
      - `425.012`

What the failed probes proved:
- `factory2-review-0020-304-309s-panel-v1-8fps` and `factory2-review-0021-423-427s-panel-v1-8fps` started too late and only produced output-only/static-edge stubs.
- `factory2-review-0022-302-307s-panel-v1-8fps` and `factory2-review-0023-421-427s-panel-v1-8fps` started earlier and did produce accepted proof carries, but those carries terminated at:
  - `304.375`
  - `423.0`
- Those two windows restated the earlier already-accepted carries; they did **not** prove the later runtime events at `305.708` or `425.012`.

Current blocker:
- The last two proof misses are not the same class as the earlier worker-overlap gaps.
- Around `305.708`, proof currently collapses into:
  - accepted carry `303.1–303.7`
  - then an `output_only_no_source_token` stub at `306.9`
  - then a later `source_without_output_settle` stub at `309.9–314.7`
- Around `425.012`, proof currently collapses into:
  - source-only track ending `421.167`
  - accepted carry `422.167–422.5`
  - then an `output_only_no_source_token` stub at `424.833`
- Important constraint:
  - a heuristic that simply lets an output-only stub inherit count authority from a nearby already-accepted carry would recover the final two in this dataset, but that would reuse prior accepted source authority and is too close to cheating the proof standard. Do **not** ship that shortcut without a much stronger product argument.

Oracle:
- A new Oracle browser session is running for the final-two question:
  - slug: `factory2-final-two`
- Prompt focus:
  - whether the final two proof misses should be solved by proof-side stitch logic, a different receipt-building strategy, or an explicit documented proof/runtime divergence.

Exact next step:
1. Read the Oracle answer for `factory2-final-two`.
2. If Oracle confirms the current evidence is insufficient for distinct proof receipts, document the explicit runtime/proof divergence for `305.708` and `425.012` instead of inventing count authority.
3. If Oracle identifies a non-cheating receipt-building move, implement it narrowly against those two timestamps only and rerun the `optimized_plus_0016_0019` proof set.

## 2026-04-29: Oracle Follow-Through for Final Two Proof Misses

What changed:
- Added proof-side source-lineage accounting in:
  - `scripts/build_morning_proof_report.py`
- Added a runtime-event-centered packet builder for unresolved proof/runtime gaps:
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
- Tightened proof-side predecessor stitching parity with runtime token lifetime in:
  - `scripts/diagnose_event_window.py`
- Added tests:
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - expanded `tests/test_build_morning_proof_report.py`
  - expanded `tests/test_diagnose_event_window.py`

What was verified:
- Focused proof/report/runtime audit suite passed:
  - `tests/test_build_morning_proof_report.py`
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - `tests/test_diagnose_event_window.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `37 passed`
- `py_compile` passed for:
  - `scripts/build_morning_proof_report.py`
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
  - `scripts/diagnose_event_window.py`
- Built the new packet artifact on the committed `21`-count proof baseline:
  - `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json`

What the new packet artifact proved:
- Runtime-only `305.708s` now packetizes as:
  - recommendation: `shared_source_lineage_no_distinct_proof_receipt`
  - prior accepted proof receipt: `factory2-review-0010-288-328s-panel-v1-5fps` track `2`
  - later stub: track `3`
  - source token key on the prior accepted receipt:
    - `factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002`
- Runtime-only `425.012s` now packetizes as:
  - recommendation: `shared_source_lineage_no_distinct_proof_receipt`
  - prior accepted proof receipt: `factory2-review-0005-396-427s-panel-v2` track `5`
  - later stub: track `6`
  - source token key on the prior accepted receipt:
    - `factory2-review-0005-396-427s-panel-v2:tracks:000001-000003-000005`
- This matches Oracle’s warning:
  - the final two proof misses currently look like an earlier accepted carry followed by an output-only/static-edge stub
  - they are **not** yet distinct proof receipts
  - do **not** close them by reusing already-consumed source authority

Important implementation notes:
- Accepted-proof dedupe can no longer rely on overlapping receipt intervals alone.
  - `scripts/build_morning_proof_report.py` now attaches:
    - `source_lineage_track_ids`
    - `source_lineage_receipt_paths`
    - `source_token_key`
  - accepted receipts are deduped by:
    - overlapping receipt intervals, or
    - shared `source_token_key`
- The packet builder must not trust `failure_link` alone when searching for output-only stubs.
  - some real stub rows still surface `reason: static_stack_edge` while the summary `failure_link` lands on `worker_body_overlap` because person-overlap flags dominate
  - stub matching now uses raw reason as well

Current blocker:
- Proof remains short of runtime truth because the last two events still lack distinct source-backed proof receipts.
- The blocker is no longer “find the timestamps.” It is:
  - build a receipt strategy that surfaces distinct new source lineage for `305.708` and `425.012`, or
  - explicitly document those two as runtime/proof divergence under the current proof bar

Exact next step:
1. Use `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json` as the canonical audit surface for the final two proof gaps.
2. Build a **new** event-centered receipt construction pass for `305.708` and `425.012` that proves fresh source lineage if it exists.
3. If that pass still collapses into the earlier accepted receipt plus later stub, stop trying to tune thresholds and record an explicit `runtime counts 23 / proof honest ceiling 21` divergence for those two events.

## 2026-04-29: Focused Final-Gap Search Result

What changed:
- Added targeted final-gap search tooling:
  - `scripts/build_factory2_final_gap_search_plan.py`
  - `scripts/run_factory2_final_gap_search.py`
  - `scripts/build_factory2_final_gap_search_report.py`
- Added tests:
  - `tests/test_build_factory2_final_gap_search_plan.py`
  - `tests/test_run_factory2_final_gap_search.py`
  - `tests/test_build_factory2_final_gap_search_report.py`
- Saved the overnight attack plan at:
  - `docs/superpowers/plans/2026-04-29-factory2-overnight-final-two-to-goal.md`

What was verified:
- New focused search suite passed:
  - `tests/test_build_factory2_final_gap_search_plan.py`
  - `tests/test_run_factory2_final_gap_search.py`
  - `tests/test_build_factory2_final_gap_search_report.py`
  - result: `9 passed`
- Combined proof/report/runtime suite also still passed after the new tooling:
  - `tests/test_build_morning_proof_report.py`
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - `tests/test_diagnose_event_window.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `46 passed`

What the search did:
- Built the bounded 8fps plan:
  - `data/reports/factory2_final_gap_search_plan.focused_v1.json`
  - `24` candidates total (`12` per final runtime-only event)
- Ran the 8fps search:
  - `data/reports/factory2_final_gap_search_run.focused_v1.json`
- Scored the 8fps search:
  - `data/reports/factory2_final_gap_search_report.focused_v1.json`
- Built the matching 10fps confirmation plan:
  - `data/reports/factory2_final_gap_search_plan.focused_v2_10fps.json`
- Ran the 10fps search:
  - `data/reports/factory2_final_gap_search_run.focused_v2_10fps.json`
- Scored the 10fps search:
  - `data/reports/factory2_final_gap_search_report.focused_v2_10fps.json`
- Wrote the explicit divergence artifact:
  - `data/reports/factory2_proof_runtime_divergence.final_two_v1.json`

What the search proved:
- For `factory2-runtime-only-0007` (`305.708s`):
  - all `12/12` focused 8fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - all `12/12` focused 10fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - pattern:
    - earlier accepted carry inside the candidate window
    - later output-only/static-edge stub near the runtime event
    - no event-local fresh proof receipt
- For `factory2-runtime-only-0008` (`425.012s`):
  - all `12/12` focused 8fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - all `12/12` focused 10fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - same pattern:
    - earlier accepted carry
    - later output-only/static-edge stub
    - no event-local fresh proof receipt

Important scorer correction:
- A naive “new `source_token_key` means fresh lineage” rule was wrong because every search diagnostic gets a new diagnostic-local namespace.
- The scorer now requires:
  - accepted proof evidence to be event-local, not just earlier in the same candidate window
  - otherwise, if a later stub follows the earlier accepted receipt, the result stays:
    - `shared_source_lineage_no_distinct_proof_receipt`

Current honest state:
- Runtime/app path: `23`
- Proof honest ceiling after targeted final-gap search: `21`
- Divergent events:
  - `305.708s`
  - `425.012s`

Exact next step:
1. Stop searching this branch by threshold/fps/window tweaking alone; the focused 8fps and 10fps sweeps both collapsed the same way.
2. Either:
  - design a brand-new receipt-construction method that can prove distinct fresh source lineage for those two events, or
  - accept the explicit divergence artifact and move the next product investment into new training/data/model work for split deliveries under worker overlap.

## 2026-04-29 23:50 - Product-Surface Count Authority Split

What was built:
- Threaded count authority through the product-facing runtime path.
- `app/services/event_ledger.py` now records `count_authority`, allows `source_token_id = null`, and accepts `approved_delivery_chain` count reasons for synthetic runtime-only events.
- `app/api/schemas.py` and `app/workers/vision_worker.py` now expose:
  - `runtime_total`
  - `proof_backed_total`
  - `runtime_inferred_only`
- Worker bookkeeping now increments those buckets from runtime event authorities while leaving manual count adjustments out of both proof/runtime-authority subtotals.

Commands run:
- `.venv/bin/python -m pytest tests/test_event_ledger.py tests/test_api_smoke.py -q`
- `.venv/bin/python -m pytest tests/test_vision_worker_states.py -q`
- `.venv/bin/python -m pytest tests/test_event_ledger.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py -q`

Results:
- `9 passed`
- `8 passed`
- `49 passed, 15 warnings`

Current state:
- Product surfaces can now report the honest split instead of one opaque total:
  - runtime total
  - proof-backed total
  - runtime-inferred-only total
- This does not change the underlying Factory2 truth state:
  - runtime/app path `23`
  - proof `21`
  - unresolved runtime-inferred-only events remain `305.708s` and `425.012s`

Next blocker:
- The remaining gap is no longer product serialization or status visibility.
- The real blocker is still proving or explicitly accepting the final `runtime 23 / proof 21` divergence for those two synthetic approved-chain deliveries.

Exact next recommended step:
1. Thread `count_authority` through any remaining persisted event-history/API consumers that still assume every count is proof-backed.
2. Add a small UI/status presentation layer that shows `runtime_total`, `proof_backed_total`, and `runtime_inferred_only` distinctly.
3. Then choose between:
  - keeping the explicit divergence as the honest shipped state, or
  - starting a new receipt-construction/model-data effort aimed only at converting the last two runtime-inferred-only events into true proof-backed receipts.

## 2026-04-29 23:59 - Frontend And Health-Snapshot Count Split

What was built:
- Extended `health_samples` persistence to store:
  - `runtime_total`
  - `proof_backed_total`
  - `runtime_inferred_only`
- Added an explicit DB migration path for older `health_samples` tables missing those columns.
- Updated the React dashboard and troubleshooting pages to surface the split directly instead of only showing an opaque hourly total.
- `Runtime Total` now reflects the operational hour total, while `Proof-Backed` and `Runtime-Inferred` make the Factory2 `23 / 21 / 2` divergence visible in-product.

Commands run:
- `.venv/bin/python -m pytest tests/test_health_repo.py tests/test_event_ledger.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_demo_mode_flow.py -q`
- `cd frontend && npm run build`
- `cd frontend && PATH="/Users/thomas/Projects/Factory-Output-Vision-MVP/.venv/bin:$PATH" npx playwright test e2e/app.spec.ts -g "dashboard and troubleshooting expose runtime versus proof-backed totals"`

Results:
- Python regression slice: `19 passed`
- Frontend production build: passed
- Playwright targeted browser check: `1 passed`

Current state:
- Product surfaces now show the honest split:
  - runtime/app total `23`
  - proof-backed total `21`
  - runtime-inferred-only total `2`
- Health snapshots persist the same split for later support/audit review.

Next blocker:
- The remaining gap is no longer hidden in product status or persisted health history.
- The actual unresolved problem is whether the final two runtime-inferred-only deliveries should remain an explicit divergence or trigger a new proof/data/model effort.

Exact next recommended step:
1. Decide whether the shipped Factory2 product should present both totals to operators as-is, or whether only support/troubleshooting surfaces should expose the split.
2. If product behavior is acceptable at `runtime 23 / proof 21`, add a small explanatory UI copy block so operators understand what `Runtime-Inferred` means.
3. If not acceptable, open the next PRD specifically for converting the final two runtime-inferred-only deliveries into fresh proof-backed receipts.

## 2026-04-30 00:21 - Final-Two Divergent Chain Review Package

What was built:
- Added a new option-2 recovery tool:
  - `scripts/build_factory2_divergent_chain_review.py`
  - `tests/test_build_factory2_divergent_chain_review.py`
- Added the next-phase PRD:
  - `docs/PRD_FACTORY2_FINAL_TWO_PROOF_CONVERGENCE.md`
- Generated a real review/training package:
  - `data/reports/factory2_divergent_chain_review.v1.json`
  - `data/datasets/factory2_divergent_chain_review_v1/`

What the package does:
- reads the runtime lineage audit + synthetic lineage report + divergence report
- reconstructs the full chain neighborhood around each unresolved runtime-only event
- extracts representative full-frame and crop images
- writes a `review_labels.csv` with placeholders for:
  - `crop_label`
  - `relation_label`

Commands run:
- `.venv/bin/python -m pytest tests/test_build_factory2_divergent_chain_review.py -q`
- `.venv/bin/python scripts/build_factory2_divergent_chain_review.py --force`

Results:
- new focused test suite: `2 passed`
- package generated successfully with:
  - `event_count: 2`
  - `item_count: 37`

Important new findings:
- `305.708s` is not just “prior accepted carry + later stub” anymore in the new package. Its full window now shows:
  - source-only tracks `104`, `105`, `106`
  - prior counted source-to-output track `107`
  - divergent output-only runtime track `108`
  - trailing output-only track `109`
- `425.012s` now shows a much richer source context than the old packet view:
  - source-only tracks `143`, `144`, `145`, `147`, `148`, `149`, `150`
  - earlier runtime output-only context `146`
  - prior counted source-to-output track `151`
  - divergent output-only runtime track `152`

Why this matters:
- The old proof rescue loop only proved the previous packet shape was insufficient.
- The new package proves the final-two problem is a chain-neighborhood review/training problem, not just a one-window threshold problem.
- This is the correct starting artifact for targeted final-two labeling and training.

Next blocker:
- The blocker is now externalized to per-item review truth, not missing extraction/plumbing.
- We still do not know whether the final two are:
  - distinct real deliveries whose source evidence needs better recovery, or
  - runtime duplicates / static residents that should be removed

Exact next recommended step:
1. Label `data/datasets/factory2_divergent_chain_review_v1/review_labels.csv`.
2. Use those labels to build the first final-two rescue dataset.
3. Only then train or patch proof/runtime logic for the final two.
