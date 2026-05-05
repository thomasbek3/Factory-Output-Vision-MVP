# PRD — Factory2 Final-Two Proof Convergence

**Status:** Active next-phase PRD  
**Created:** 2026-04-29 EDT  
**Owner:** Thomas Bekkers  
**Repo:** `/Users/thomas/Projects/Factory-Output-Vision-MVP`

## 2026-05-01 App Runtime Update

The runtime/app side of Factory2 is now verified in the actual visible app path at true real-time speed:

```text
dashboard-started app run
FC_DEMO_COUNT_MODE=live_reader_snapshot
FC_COUNTING_MODE=event_based
FC_DEMO_LOOP=0
FC_PROCESSING_FPS=10
FC_READER_FPS=10
Runtime Total: 23
truth comparison: 23/23
wall_per_source: 1.0
```

Primary artifact:

```text
data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json
```

This update does not resolve the proof-backed final-two question below. It does establish that the actual app can count the Factory2 human-truth total from real processed frames at real-time speed. The remaining final-two work is proof/evidence authority and future generalization, not basic runtime correctness on `factory2.MOV`.

## 1. Problem

Factory2 currently has:

```text
runtime_total = 23
proof_backed_total = 21
runtime_inferred_only = 2
```

The remaining unresolved events are:

- `305.708s`
- `425.012s`

Those events are operationally counted through runtime-approved delivery chains, but proof still cannot mint a fresh, discrete source-backed receipt for them.

## 2. Why the old approach stalled

The previous rescue loop was too narrow:

- focused `5/8/10fps` proof-window searches
- prior-accepted-receipt vs later-output-stub comparisons

That proved the current proof packet shape was insufficient, but it did **not** prove the events were fake. It only proved that the old packetization could not recover them honestly.

## 3. New first-principles thesis

The next recovery unit is not “one more proof window.”

It is a **divergent chain neighborhood**:

- source-anchor track
- nearby source-only context tracks
- prior runtime/proof delivery in the same window
- divergent runtime output-only track
- trailing output resident/context tracks

For the final two, the chain neighborhoods are richer than the old proof receipts exposed:

### 305.708s window

```text
source-only:       104, 105, 106
prior runtime/proof: 107  (source_to_output, counted at 303.508s)
divergent runtime: 108  (output_only, counted at 305.708s)
trailing output:   109
```

### 425.012s window

```text
source-only:       143, 144, 145, 147, 148, 149, 150
earlier runtime context: 146  (synthetic output-only count at 401.711s)
prior runtime/proof: 151  (source_to_output, counted at 422.612s)
divergent runtime: 152  (output_only, counted at 425.012s)
```

That means the next effort must be chain reconstruction + labeling/training, not more threshold nudging.

## 4. Goal

Convert the remaining `runtime_inferred_only` events into one of two honest outcomes:

1. **Recovered proof-backed counts**
   - new evidence construction or targeted model work yields fresh source-backed receipts
   - proof rises from `21` to `23`

2. **Confirmed runtime false positives or irreducible non-proof events**
   - review/training shows they are not distinct carried panels, or still not provable
   - runtime logic must be corrected, or the divergence remains explicit

The terminal goal is still:

```text
factory2 runtime/app count = 23
factory2 proof count = 23
false positives = 0
```

## 5. Built so far

New review artifact:

```text
data/reports/factory2_divergent_chain_review.v1.json
data/datasets/factory2_divergent_chain_review_v1/
```

Built by:

```bash
.venv/bin/python scripts/build_factory2_divergent_chain_review.py --force
```

What it contains:

- full chain-neighborhood track summaries for the two unresolved events
- extracted full-frame review images
- extracted crops
- review CSV placeholders for:
  - `crop_label`
  - `relation_label`

## 6. Milestones

### Milestone 1 — Chain-Neighborhood Review Package

Status: **Done**

Deliverables:

- `scripts/build_factory2_divergent_chain_review.py`
- `tests/test_build_factory2_divergent_chain_review.py`
- `data/reports/factory2_divergent_chain_review.v1.json`
- `data/datasets/factory2_divergent_chain_review_v1/`

Success criteria:

- package is reproducible
- both unresolved events have auditable source/context/output neighborhoods
- extracted assets are ready for human or model-focused review

### Milestone 2 — Relation Labeling

Status: **Done (draft local labels)**

Label the review CSV for the final-two package.

Required labels:

```text
crop_label:
- carried_panel
- worker_only
- static_stack
- unclear

relation_label:
- distinct_new_delivery
- same_delivery_as_prior
- static_resident
- unclear
```

Goal:

- decide whether the divergent runtime output-only track is a true new delivery
- decide which source-only context tracks belong to that delivery, if any

Current local state:

- `data/datasets/factory2_divergent_chain_review_v1/review_labels.csv` now has a conservative draft pass
- all `37` reviewed crops are currently labeled `crop_label = carried_panel`
- current relation-label counts:
  - `same_delivery_as_prior: 21`
  - `distinct_new_delivery: 5`
  - `unclear: 11`
- the draft labels should be treated as review seed truth, not as final converged labels

### Milestone 3 — Targeted Rescue Dataset

Status: **Done**

From the labeled chain package, export a tight final-two rescue dataset:

- positive source fragments for the unresolved deliveries
- positive output fragments for the unresolved deliveries
- hard negatives from static resident/output-edge context
- nearby worker-overlap negatives

This dataset is specifically for the final-two convergence problem, not generic Factory2 training.

Built locally:

```text
data/reports/factory2_static_resident_reference_crops.v1.json
data/datasets/factory2_static_resident_reference_crops_v1/
data/reports/factory2_final_two_rescue_dataset.v1.json
data/datasets/factory2_final_two_rescue_dataset_v1/
```

Current rescue-dataset state:

- `eligible_item_count: 30`
- `skipped_unclear_relation_count: 11`
- relation labels:
  - `distinct_new_delivery: 5`
  - `same_delivery_as_prior: 21`
  - `static_resident: 4`
- split counts:
  - `train: 18`
  - `val: 7`
  - `test: 5`
- `ready_for_training: true`

### Milestone 4 — Targeted Model / Evidence Pass

Status: **In progress**

Use the rescue dataset to improve one of:

- source-side detector recall in the final-two pattern
- split-track lineage association
- second-stage crop classifier for distinguishing true new delivery vs stack-edge resident

Current result:

- the first honest Milestone 4 slice is **chain-level adjudication**, not a single-crop relation classifier
- a local single-crop baseline was not convincing enough to trust:
  - tiny dataset
  - missing class coverage in `val`
  - weak top-1 behavior even after full draft labeling
- Oracle’s recommendation was to adjudicate the final two as duplicate/runtime-chain problems first

First bounded Milestone 4 deliverable:

```text
scripts/build_factory2_final_two_chain_adjudication.py
data/reports/factory2_final_two_chain_adjudication.v1.json
data/datasets/factory2_final_two_chain_adjudication_v1/
tests/test_build_factory2_final_two_chain_adjudication.py
```

Expected current outcome from that adjudicator:

- `305.708s` -> `duplicate_of_prior_runtime_event` (`303.508s`)
- `425.012s` -> `duplicate_of_prior_runtime_event` (`422.612s`)
- `proof_action = do_not_mint` for both

### Milestone 5 — Honest Proof Rerun

After targeted model/evidence changes:

1. rebuild the divergent review package
2. rerun the proof artifacts
3. accept success only if the final two become genuinely proof-backed

## 7. Non-negotiable rules

1. Do not promote the final two by reusing already-consumed source authority.
2. Do not raise proof counts by just relaxing the synthetic fallback guard.
3. Do not assume runtime `23` is correct at the per-event level just because the total matches human truth.
4. Every recovery attempt must preserve auditable receipts.
5. If the final-two review proves runtime counted duplicates or residents, fix runtime rather than forcing proof up.

## 8. Immediate next step

Do not stop at the rescue-dataset export. The next honest move is Milestone 4:

1. decide whether the final-two rescue problem is learnable from single crops at all, or whether it needs pairwise/sequence lineage context
2. keep the chain-level adjudication artifact as the first authority layer for duplicate/static/source-authority suppression
3. only build a learned model if it operates at the right unit of evidence, not a mislabeled crop-only shortcut
4. feed the resulting evidence back into proof/runtime without reusing already-consumed source authority
