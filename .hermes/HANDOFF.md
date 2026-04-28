# Factory Vision Hermes Handoff

Updated: 2026-04-28 11:27:38 EDT
Repo: `/Users/thomas/Projects/Factory-Output-Vision-MVP`
Branch: `main`



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
