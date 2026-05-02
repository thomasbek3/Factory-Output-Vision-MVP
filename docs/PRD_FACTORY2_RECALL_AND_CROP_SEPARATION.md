# PRD — Factory2 Recall Recovery And Crop-Level Separation

**Status:** Proposed next PRD  
**Created:** 2026-04-28 EDT  
**Owner:** Thomas Bekkers  
**Repo:** `/Users/thomas/Projects/Factory-Output-Vision-MVP`  
**Prior PRD:** [PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md](/Users/thomas/Projects/Factory-Output-Vision-MVP/docs/PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md)  

> 2026-05-01 status note: this PRD is now historical for the runtime/app path. The actual app path has been verified on `factory2.MOV` at real-time speed with `Runtime Total 23` and truth comparison `23/23` in `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json`. The remaining value of this PRD is its proof/crop-separation doctrine: do not loosen thresholds, preserve evidence, and use hard-case crops/model work for generalization.

**Canonical proof command:**

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

---

## 1. Product problem

The project goal is still unchanged:

```text
factory2.MOV should count all 23 real carried-panel transfers with no false positives.
```

The current system is no longer blocked by count architecture. It is blocked by two linked recall problems:

1. **Mixed event windows undercount.**
   Broad windows merge multiple carries and starve the perception layer of clean receipts.
2. **Worker-overlap perception is still too weak on the remaining hard cases.**
   Some tracks already have the right temporal path, but the system still cannot reliably prove panel vs worker on the crop itself.

This PRD exists to attack both problems directly:

- recover more true carries with **narrow, event-centered proof windows**
- build a **hard-case crop dataset** from blocked receipts so panel-vs-worker separation can improve with targeted training

---

## 2. Current verified state

### 2.1 Broad proof baseline

Current resampled broad-window baseline:

```text
data/reports/factory2_morning_proof_report.candidate6_resampled.json
accepted_count: 8
suppressed_count: 41
uncertain_count: 23
```

This matters because it proves the denser-receipt patch helped, but it also proves the old broad proof set is not enough.

### 2.2 Narrow-window proof results

Focused windows already outperform the broad mixed windows in isolation:

```text
0–30s        -> accepted_count: 1
145–185s     -> accepted_count: 1
232–272s     -> accepted_count: 2
288–328s     -> accepted_count: 1
332–372s     -> accepted_count: 1
372–412s     -> accepted_count: 2
```

Representative artifacts:

```text
data/reports/factory2_morning_proof_report.review0014_000_030.json
data/reports/factory2_morning_proof_report.review0012_145_185.json
data/reports/factory2_morning_proof_report.review0008_232_272_resampled.json
data/reports/factory2_morning_proof_report.review0010_288_328.json
data/reports/factory2_morning_proof_report.review0009_332_372_resampled.json
data/reports/factory2_morning_proof_report.review0011_372_412.json
```

### 2.3 What the evidence says

The system is recovering real counts when:

- receipts keep more representative observations
- dense periods are split into narrower windows
- person/panel separation runs on those denser receipts

The system still misses carries when:

- a broad diagnostic window merges multiple carries into one muddled proof surface
- source-only tracks never get later output completion in the same diagnostic window
- worker-overlap crops still lack a sufficiently strong panel-vs-body signal

---

## 3. First-principles thesis

The next unlock will not come from threshold loosening.

It will come from two product moves:

1. **Proof-window restructuring**
   Build the best possible non-overlapping or intentionally deduped recall-oriented proof set from narrow windows.
2. **Crop-level hard-case learning**
   Export the blocked worker-overlap receipts into a labeling/training dataset aimed at panel-vs-worker separation.

This is the right direction because:

- temporal path evidence is often already present
- the remaining ambiguity lives in the crop
- digital zoom alone does not create new pixels, but tight crops plus labels are the right training input for a second-stage classifier or segmenter

---

## 4. Product goal

### Immediate phase goal

Replace the current broad undercounting proof set with a narrower recall-oriented proof set that yields materially more accepted counts without opening false positives.

### Next phase goal

Create a dedicated hard-case crop dataset from blocked worker-overlap receipts to support panel-vs-worker classification or segmentation training.

### Terminal project goal

```text
factory2.MOV runtime/app path = 23 counts
factory2.MOV proof path = 23 accepted counts
false positives = 0
```

---

## 5. Non-negotiable doctrine

1. Do not lower thresholds just to inflate counts.
2. Do not count from detector boxes alone.
3. Do not treat digital zoom as new evidence.
4. Proof receipts stay auditable; every accepted count must retain source/output/separation receipts.
5. Narrow-window recall gains must survive deduplication and overlap review.
6. Crop dataset exports are training evidence, not count approvals.
7. If a carry is still not visually defensible, it stays suppressed or uncertain.

---

## 6. Scope

### In scope

- narrow-window recall proof construction
- merged proof-set deduplication
- blocked-receipt crop export
- label schema for crop review
- optional Roboflow-compatible dataset packaging
- second-stage training PRD hooks

### Out of scope

- generic UI work
- changing product definition of done
- pretending proof-only success is enough
- global retraining without first exporting the actual blocked receipts
- fake super-resolution claims

---

## 7. Milestones

### Milestone 1 — Stable narrow-window proof set

Create a stable merged proof set built from the best narrow windows instead of the old broad windows.

Expected ingredients:

```text
0–30s
0–78s or its non-overlapping substitute
98s anchor window
145–185s
222s anchor window
232–272s
288–328s
332–372s
372–412s
422s tail window
```

Requirements:

- each window must be justified by accepted receipts or a clear missing-evidence reason
- overlapping windows must be explicitly deduped
- merged proof artifact must be reproducible from a documented command

Deliverables:

```text
data/reports/factory2_morning_proof_report.<new-merged>.json
data/reports/factory2_morning_proof_run_summary.<new-merged>.json
```

Success criterion:

```text
merged proof accepted_count > 8
with no false-positive regression in the suppressed/static/worker-overlap buckets
```

### Milestone 2 — Blocked receipt crop exporter

Create:

```text
scripts/export_factory2_blocked_crops.py
tests/test_export_factory2_blocked_crops.py
```

Inputs:

- proof report decision receipt index
- blocked worker-overlap receipts
- separation sidecars
- crop assets already generated under `track_receipts/*-crops/`

Outputs:

```text
data/reports/factory2_blocked_crop_dataset.json
data/datasets/factory2_blocked_crops/
```

Each crop item must include:

- diagnostic/window id
- track id
- timestamp
- source/output zone
- current gate decision/reason
- person overlap
- outside-person ratio
- person/panel separation recommendation
- crop path
- optional full-frame/receipt-card path
- label placeholder:

```json
{
  "crop_label": "carried_panel | worker_only | static_stack | unclear",
  "mask_status": "missing | panel_mask_only | worker_and_panel_masks",
  "notes": ""
}
```

### Milestone 3 — Label-ready packaging

Package the blocked crop dataset so it can be reviewed either:

- locally
- or in Roboflow as a private annotation project

The export format must support:

- plain filesystem review
- JSON manifest-driven review
- optional Roboflow upload workflow later

No credentials in repo. No automatic upload in this milestone.

### Milestone 4 — Second-stage model PRD hook

Once the dataset exists, define the immediate training target:

- crop classifier:
  `carried_panel` vs `worker_only` vs `static_stack`

or

- crop segmenter:
  panel mask + worker mask

This milestone only requires:

- training interface definition
- evaluation target definition
- integration points into proof/runtime gate

It does not require shipping the trained model yet.

---

## 8. Technical requirements

### 8.1 Narrow-window proof requirements

- preserve the existing proof report format
- keep Python 3.9 compatibility
- avoid mutating shared diagnostics in ways that corrupt later merged runs
- prefer frozen/copy-on-write proof diagnostics for merged experiments

### 8.2 Crop export requirements

- no image synthesis
- no lossy relabeling of existing evidence
- all exported crops must trace back to a real receipt path
- dataset manifest must record provenance for every crop

### 8.3 Training-data quality requirements

- crops must include enough context around the panel candidate to distinguish body vs mesh vs stack
- blocked high-priority receipts should be exported first
- accepted carries should also be exported as positives so the training set includes both sides of the boundary

---

## 9. Verification

Minimum verification for this PRD:

```bash
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_export_factory2_blocked_crops.py tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py -q
```

For proof-set work:

```bash
.venv/bin/python scripts/run_factory2_morning_proof.py --force --diagnostic ...
```

For merged proof replacement:

```bash
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

only after the new default diagnostic set is intentionally updated.

---

## 10. Risks

1. Narrow windows can introduce duplicate counts if overlaps are not explicitly deduped.
2. Some true carries may still be visually unresolvable from this camera angle.
3. Blocked crop labels may still need manual effort; auto-labeling on wire mesh is not assumed to be reliable.
4. Training a crop-level model may improve precision before recall, or vice versa.
5. Shared mutable diagnostic directories can contaminate merged proof experiments if not frozen.

---

## 11. Definition of done

### This PRD is done when

1. a stable merged narrow-window proof set exists and clearly beats the current broad baseline of `8`
2. a blocked-receipt crop dataset exists on disk with provenance and label placeholders
3. the next training target for panel-vs-worker separation is concretely defined

### The overall Factory2 project is still not done until

```text
factory2.MOV runtime/app path counts 23
AND proof path accepts 23
AND false positives remain 0
```

This PRD is the next step toward that end, not the end itself.
