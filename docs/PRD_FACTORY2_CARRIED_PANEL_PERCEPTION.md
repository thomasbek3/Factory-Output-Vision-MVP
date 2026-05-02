# PRD — Factory2 Carried-Panel Perception Reset

**Status:** Active PRD / work from this document  
**Created:** 2026-04-28 10:40 EDT  
**Owner:** Thomas Bekkers  
**Repo:** `/Users/thomas/Projects/Factory-Output-Vision-MVP`  
> 2026-05-01 status note: this PRD describes the earlier perception reset before the runtime/app path converged. The actual app now counts `factory2.MOV` from real processed frames at `1.0x` and matches the human truth ledger `23/23` in `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json`. Keep the doctrine here for future videos: counts must remain auditable, and worker/body overlap should be solved with stronger evidence rather than threshold loosening.

**Canonical proof command:**

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

---

## 1. Product problem

`factory2.MOV` is representative factory footage where a human can infer/count panel transfers, but the current system still correctly abstains:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
```

This is no longer mainly a count-state-machine problem. The count architecture is doing the right thing by refusing weak evidence. The missing capability is perception: proving that a **discrete carried wire-mesh panel** exists separately from worker body/arms/clothing/background/static-stack edges.

The current architecture sees detector boxes, zones, person-box overlap, crop texture, and track motion. A human uses temporal context, hand-object relationship, source pickup, output placement, and object permanence through occlusion. This PRD exists to close that gap without hallucinating counts.

---

## 2. Non-negotiable doctrine

1. **Raw detections are observations, not counts.**
2. **Crop texture is triage, not approval.**
3. **Single-frame protrusion is not enough.**
4. **A count requires a perception-gate-approved source token consumed exactly once.**
5. **Worker/body overlap can be challenged only with stronger evidence, not by loosening thresholds.**
6. **Every accepted, suppressed, or uncertain event needs receipts.**
7. **VLMs/Oracle can audit packets and propose labels/masks; raw VLM counting is not the counter.**
8. **Do not optimize for a nonzero count. Optimize for a defensible count.**

---

## 3. Current verified state

Latest relevant committed slice:

```text
e40ea6f feat: add panel crop evidence probe
```

Recent proof summary:

```text
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
panel_texture_candidate_receipts: 4
low_panel_texture_receipts: 6
```

Known useful artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/reports/factory2_panel_crop_evidence.json
```

The prior top work item, event0002 track 7, has partial outside-person evidence but is a weak count-cracking target because it is too ambiguous/sparse. It remains useful as an ambiguity/control case.

The next candidates should be long worker-entangled tracks with stronger source/output temporal evidence, especially:

```text
event0002 track 5
event0006 track 1
event0006 track 4
event0002 track 2
event0002 track 7  # ambiguity/control, not primary unlock
```

---

## 4. Product goal

Build an auditable perception layer that can answer, for representative factory footage:

> Is there a discrete wire-mesh panel being carried from the source/process area toward output, separable enough from worker/static-stack/background to mint a source token?

The first product target is not “count everything.” The target is:

```text
factory2.MOV
→ temporal transfer review packets
→ reviewer/AI labels: countable_panel | not_panel | insufficient_visibility
→ person/panel separation evidence
→ source-token decision receipts
→ proof report preserving accepted/suppressed/uncertain counts
```

---

## 5. Users and use cases

### Primary user

Factory owner/operator who wants a cheap camera appliance that counts output without enterprise Cognex/Keyence/MES complexity.

### Internal user

Thomas/agent loop proving whether the hard representative footage is solvable with auditable AI perception.

### Core use cases

1. **Trusted count:** worker carries new panel from source/process to output → count 1.
2. **Correct suppression:** worker moves/repositions already-output panel → count 0.
3. **Correct abstention:** footage does not visibly prove a carried panel separate from worker/static stack → accepted count remains 0 and report explains why.
4. **Learning loop:** suppressed/uncertain receipts become hard negatives, review packets, or active-panel labels for the next model/perception iteration.

---

## 6. Acceptance criteria

### 6.1 Transfer review packets

A new packet builder must emit temporal evidence packets for the strongest worker-entangled tracks.

Required output:

```text
data/reports/factory2_transfer_review_packets.json
data/diagnostics/event-windows/.../track_receipts/track-000005-transfer-packet.json
data/diagnostics/event-windows/.../track_receipts/track-000005-transfer-packet.jpg
```

Each packet must include:

- event/window id
- track id
- current gate decision/reason
- source frame count
- output frame count
- max displacement
- flow coherence, when available
- person-overlap metrics, when available
- static-stack/resident evidence, when available
- selected full-frame/overlay/crop paths
- before/during/after frame roles
- review question
- label fields for reviewer/VLM/AI audit

Packet ranking must prioritize:

```text
source/output continuity
source_frames
output_frames
max_displacement
flow_coherence
non-static evidence
```

It must penalize:

```text
single-frame evidence
output-only evidence
static-stack overlap
low/no displacement
```

Success means the top packet list starts with long temporal candidates, not merely the highest outside-person ratio.

### 6.2 Review label schema

The packet artifact must support this review shape:

```json
{
  "track_id": 5,
  "reviewer": "human_or_vlm_or_ai",
  "discrete_panel_visible": true,
  "separable_from_worker": true,
  "source_origin_supported": true,
  "output_entry_supported": true,
  "should_mint_source_token": true,
  "should_increment_count": true,
  "evidence_frame_indices": [12, 19, 25, 31],
  "notes": "visible mesh panel carried through source to output"
}
```

Labels are evidence for development. They do not automatically change product counts until gate logic is implemented and tested.

### 6.3 Person/panel separation probe

After transfer packets exist, add a diagnostic layer that produces per-frame separation evidence:

```json
{
  "track_id": 5,
  "frame_path": "...",
  "panel_box": [0, 0, 0, 0],
  "person_box": [0, 0, 0, 0],
  "person_mask_path": "...",
  "candidate_panel_mask_path": "...",
  "visible_non_person_panel_area": 12345,
  "visible_non_person_panel_ratio": 0.27,
  "panel_boundary_score": 0.62,
  "mesh_texture_score": 0.08,
  "separation_decision": "separable_panel_candidate"
}
```

This may use person masks, pose/keypoints, SAM/SAM2, optical flow, or VLM-assisted masks offline, but it must save visual/JSON receipts. No hidden vibes.

### 6.4 Source-token threshold

A track may become eligible for a source token only if all are true:

1. Visible panel evidence exists in at least 3 sampled frames, or 2 strong frames plus source/output context.
2. The visible panel region is not explainable as clothing, arms, torso, static stack, background, or detector jitter.
3. There is person separation: panel evidence persists outside the person silhouette/mask, not merely outside a coarse person bbox.
4. The same candidate persists through time with coherent transfer motion.
5. First credible evidence occurs in source/transfer context, not output-only.
6. Static-stack/resident/reposition suppressors pass.

A count increment additionally requires output completion evidence:

```text
same source-token panel enters output zone, settles into output stack, or disappears into output stack with before/after support
```

---

## 7. Implementation plan

### Milestone 1 — Temporal transfer review packets

Create:

```text
scripts/build_panel_transfer_review_packets.py
tests/test_build_panel_transfer_review_packets.py
```

Inputs:

```text
data/reports/factory2_morning_proof_report.json
data/diagnostics/event-windows/*/diagnostic.json
track_receipts/*.json
track_receipts/*-sheet.jpg
track_receipts/*-crops/*.jpg
```

Outputs:

```text
data/reports/factory2_transfer_review_packets.json
track-*-transfer-packet.json
track-*-transfer-packet.jpg
```

TDD requirements:

- test ranking prefers long source/output temporal evidence over single-frame protrusion;
- test packet schema contains review fields and asset paths;
- test no-overwrite unless `--force`;
- test missing optional assets degrade gracefully with warnings, not crashes.

Verification:

```bash
python -m pytest tests/test_build_panel_transfer_review_packets.py -q
python -m py_compile scripts/build_panel_transfer_review_packets.py tests/test_build_panel_transfer_review_packets.py
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
```

### Milestone 2 — Packet audit pass

Run a bounded AI/VLM or human-style audit over the top packets.

Outputs:

```text
data/reports/factory2_transfer_review_packet_audit.json
```

Required summary:

```text
countable_panel: N
not_panel: N
insufficient_visibility: N
primary_failure_link: panel_vs_worker_separation | source_origin | output_entry | static_stack | sampling
```

No count logic changes in this milestone.

### Milestone 3 — Person-mask/pose-aware separation

Create:

```text
scripts/analyze_person_panel_separation.py
tests/test_analyze_person_panel_separation.py
```

The first version can be diagnostic-only. It should compare candidate panel evidence to person silhouette/mask/pose, then write separation receipts.

TDD requirements:

- synthetic protruding panel outside person silhouette → `separable_panel_candidate`;
- worker/body-only region inside person silhouette → `worker_body_overlap`;
- static-stack/background edge → reject/uncertain;
- Python 3.9-compatible runtime typing.

### Milestone 4 — Gate integration only after evidence passes

Only after real packet/separation evidence proves a discrete carried panel, integrate into `app/services/perception_gate.py` and proof reports.

Required tests:

- countable source→output panel now can mint source token;
- worker/body false positive still rejected;
- output-only/static-stack candidate still rejected;
- hard-negative eval remains clean.

Canonical verification:

```bash
python -m pytest tests/test_perception_gate.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py -q
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

---

## 8. Out of scope for this PRD

- General UI polish.
- New repo creation.
- Cloud dashboards.
- Beam sensor work.
- Lowering confidence thresholds to force nonzero counts.
- Counting directly from VLM text answers.
- Generic model comparison unless it targets worker-entangled active carried panels.

---

## 9. Risks

1. `factory2.MOV` may be human-countable through broader contextual inference while lacking enough visible evidence for auditable product counting.
2. Person masks may swallow the carried panel if the model treats panel+worker as one silhouette.
3. VLM/AI packet audits may disagree, which means the evidence is still not product-grade.
4. A model can overfit factory2 and fail on other videos unless held-out clips/hard negatives remain in the loop.
5. Camera angle may remain the cheapest real fix. The PRD should prove whether perception can crack this footage, not pretend camera setup does not matter.

---

## 10. Definition of done

This PRD is satisfied when one of the following is true:

### Success path

```text
factory2.MOV proof run produces at least one accepted count
AND every accepted count has temporal packet + person/panel separation receipts
AND hard-negative/static-stack/worker-body cases remain suppressed
AND rerun command is documented
```

### Honest failure path

```text
factory2.MOV still has accepted_count: 0
BUT transfer packets + separation receipts prove the missing physical evidence link
AND the report recommends the next product move: labels/model, segmentation/pose, denser sampling, calibration, or camera setup
```

Both outcomes are useful. Fake counts are not.
