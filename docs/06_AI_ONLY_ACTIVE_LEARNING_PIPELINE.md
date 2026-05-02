# AI-Only Active Learning Pipeline

Updated: 2026-05-02

## Purpose

Factory Vision counts live with AI only. The authoritative live runtime path remains YOLO/event-based counting in the app. VLMs, teacher models, Moondream, Moondream Lens, and human/VA reviewers are offline helpers for evidence review, labeling, audits, troubleshooting, and future model promotion.

Product pitch:

```text
Counts live with AI only. Learns from recorded edge cases. Optional overnight review improves future accuracy.
```

## Runtime Count Rule

Live counting must not block on a human or cloud model. During a shift, Runtime Total comes only from the configured app counting path:

```text
camera or file-backed source
  -> ordered frames
  -> YOLO/event-based counting
  -> runtime count event
  -> dashboard Runtime Total
```

The runtime path must not call a VLM before incrementing, wait for a human reviewer, or self-train mid-shift. Operator correction controls remain a separate oversight mechanism and are not validation proof.

## Evidence Packets

An evidence packet is an offline, reviewable record around a runtime event or suspected miss. It should be deterministic and include:

- case/video identity and source video hash
- source artifact paths
- runtime model/settings metadata
- event timestamp and frame index when available
- review window start/end timestamps
- count event payload copied from the app artifact
- duplicate, miss, occlusion, and confidence risk fields
- privacy mode
- label tier/status fields that start as bronze unless promoted

Evidence packets are not count authority. They are inputs to audit, labeling, and training workflows.

Current extractor:

```bash
.venv/bin/python scripts/extract_event_windows.py \
  --case-id img3254_clean22_candidate \
  --extract-review-frames \
  --frame-output-dir data/reports/active_learning/review_frames/img3254_clean22 \
  --output data/reports/active_learning/img3254_event_evidence.v1.json \
  --force
```

Without `--extract-review-frames`, the script writes metadata only. With it, the script writes deterministic per-window JPEG review frames and records frame paths/hashes in each window.

## Uncertain Event Capture

The active-learning loop should collect:

- counted runtime events
- low-confidence or high-risk event windows
- duplicate-risk neighborhoods
- possible miss windows from truth/app divergence analysis
- negative/background windows from idle regions

Collection is allowed during or after operation, but promotion is offline. No captured uncertain event can change the live Runtime Total after the fact.

## AI Adjudicator Role

An AI adjudicator may be a frontier VLM teacher, Moondream/local VLM, Moondream Lens, or future specialist model. Its job is to produce structured suggestions such as:

- `countable`
- `completed`
- `in_transit`
- `static_stack`
- `worker_only`
- `unclear`

AI adjudicator output must include provider/model metadata, prompt or fixture version, confidence, duplicate risk, miss risk, and review status. It is a suggestion, not truth. Dry-run/local fixture mode is the default for scripts in this repo; cloud calls require explicit future configuration and permission.

Current Moondream audit entry point:

```bash
.venv/bin/python scripts/moondream_audit_events.py \
  --evidence data/reports/active_learning/img3254_event_evidence.v1.json \
  --provider dry_run_fixture \
  --output data/reports/active_learning/img3254_moondream_audit.dry_run_v1.json \
  --force
```

To use a local Moondream Station instance:

```bash
moondream-station
.venv/bin/python scripts/moondream_audit_events.py \
  --evidence data/reports/active_learning/img3254_event_evidence.v1.json \
  --provider moondream_station \
  --endpoint http://127.0.0.1:2020/v1 \
  --output data/reports/active_learning/img3254_moondream_audit.local_v1.json \
  --force
```

The Station provider is localhost-gated by default. It refuses nonlocal endpoints unless a future caller explicitly opts out of that guard.

## Review Queue

Teacher labels are raw advisory output. Convert them into a reviewer-ready queue before asking a human or VA to inspect frames:

```bash
.venv/bin/python scripts/build_review_queue.py \
  --evidence data/reports/active_learning/img3254_event_evidence.frames_v2.json \
  --teacher-labels data/reports/active_learning/img3254_moondream_audit.local_v2.json \
  --output data/reports/active_learning/img3254_review_queue.local_v1.json \
  --force
```

The queue ranks `unclear`, low-confidence, duplicate-risk, miss-risk, and hard-negative candidates ahead of routine entries. Queue entries stay `bronze`/`pending` with `validation_truth_eligible=false` and `training_eligible=false`; they are instructions for review, not approved labels.

Export a static contact sheet when the queue needs a quick human pass:

```bash
.venv/bin/python scripts/export_review_queue_html.py \
  --queue data/reports/active_learning/img3254_review_queue.local_v1.json \
  --output data/reports/active_learning/img3254_review_queue.local_v1.html \
  --force
```

The HTML is local/offline and uses relative frame links. It is still advisory only: checking items in the browser does not promote anything to validation truth or training data.

## Optional Overnight Human/VA Review

Human or VA review is optional and after-the-fact. It can:

- approve or reject teacher suggestions
- reconcile conflicts between app events, teacher labels, and truth ledgers
- promote reviewed labels into gold
- keep unclear cases in bronze/review queue

Human review is never required for live counting. The app must keep counting even if no reviewer is available.

## Label Tiers

| Tier | Authority | Allowed Uses |
| --- | --- | --- |
| `gold` | human-approved or reconciled verified truth | validation proof, regression truth, supervised training/evaluation |
| `silver` | high-confidence AI-agreed labels with safeguards | training experiments, triage, never validation truth |
| `bronze` | raw candidates, teacher suggestions, unclear labels | review queue only |

Rules:

- Teacher/VLM output starts as `bronze` and `pending`.
- `bronze` and `pending` labels cannot enter validation truth.
- `silver` labels can support training experiments only when the dataset manifest says so and split leakage checks pass.
- `gold` requires explicit review/reconciliation metadata.

## Privacy Modes

| Mode | Meaning |
| --- | --- |
| `offline_local` | all footage, labels, and audits stay on the edge/dev machine or LAN |
| `cloud_assisted_setup` | customer-approved setup/training footage may be sent to a cloud teacher for labeling acceleration |
| `cloud_assisted_audit` | customer-approved saved clips may be sent to a cloud model for offline audit |

Default mode is `offline_local`. Factory footage must not be silently sent to cloud providers. Cloud-assisted modes require explicit permission, non-sensitive or approved footage, and provider metadata in the output artifact.

Moondream Station is the preferred first Moondream integration because it keeps inference local behind `http://127.0.0.1:2020/v1`. The repo does not require the Moondream Python package for default tests or dry-run operation.

## Model Promotion Gate

New model/settings candidates must pass the registry validation set and any customer-specific cases before promotion. Promotion requires:

- no runtime code path that depends on VLM or human approval
- clean registry case results through `scripts/validate_video.py` or equivalent real-app proof
- no teacher/VLM labels used as validation truth
- train/test splits checked for event/window leakage
- documented model/settings metadata
- Test Case 1 remains intact

## Non-Goals

- No VLM runtime count authority.
- No required human live review.
- No cloud calls by default.
- No self-training during a live shift.
- No teacher labels written directly into validation truth.
- No timestamp replay, fake UI updates, or offline retrospective count presented as app proof.
- No video-specific hacks for Factory2, IMG_3262, IMG_3254, or future cases.
