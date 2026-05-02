# Validation Pipeline

This is the productized path for adding or rechecking a factory video.

## Goal

Each video candidate should end with a manifest, truth ledger, observed app events, app-vs-truth comparison, pacing evidence, and a final validation report. A clean final total with wrong timing is not done.

## Inputs

- Source video copied into the repo working cache, usually under `data/videos/from-pc/` or `demo/`.
- Durable local copy under `/Users/thomas/FactoryVisionArtifacts/videos/raw/` when the video should be retained.
- Video SHA-256 and ffprobe metadata.
- Reviewed human truth rule and timestamped truth ledger.
- Model/settings manifest.
- Real app launch settings.

Artifact storage policy lives in `docs/07_ARTIFACT_STORAGE.md` and `validation/artifact_storage.json`. Do not put raw factory videos in normal Git; record artifact paths and hashes in manifests instead.

## Stages

1. Register or update the video manifest.
2. Fingerprint the video with SHA-256.
3. Copy or verify the raw video in the local artifact root.
4. Probe duration, codec, resolution, and frame rate.
5. Generate preview/review sheets.
6. Lock the truth rule before final proof.
7. Build a timestamped human truth ledger.
8. Launch the real app stack.
9. Open the dashboard and click `Start monitoring`.
10. Capture backend observed events.
11. Compare observed events to the truth ledger.
12. Measure wall/source pacing.
13. Write a final validation report.
14. Update `validation/registry.json`.

## Real App Requirements

The proof run must use:

```text
FC_DEMO_COUNT_MODE=live_reader_snapshot
FC_COUNTING_MODE=event_based
FC_DEMO_PLAYBACK_SPEED=1.0
```

The user flow must be:

```text
Open dashboard
Click Start monitoring
See the candidate video name
Runtime Total starts at 0
Runtime Total increments at completed-placement moments
Demo completes at the chosen truth total
```

## Command Entry Points

Bootstrap a new candidate so the first pass reuses the prior validated path instead of starting from scratch:

```bash
.venv/bin/python scripts/bootstrap_video_candidate.py \
  --case-id new_candidate \
  --video data/videos/from-pc/NEW_VIDEO.MOV \
  --expected-total 25 \
  --baseline-case-id img2628_candidate \
  --preview \
  --force
```

Screen detector transfer before running a full real-time proof:

```bash
.venv/bin/python scripts/screen_detector_transfer.py \
  --video data/videos/from-pc/NEW_VIDEO.MOV \
  --model models/img2628_worksheet_accept_event_diag_v1.pt \
  --model models/img3254_active_panel_v4_yolov8n.pt \
  --model models/img3262_active_panel_v2.pt \
  --output data/reports/new_candidate_detector_transfer_screen.v1.json \
  --force
```

Plan or execute from a manifest:

```bash
.venv/bin/python scripts/validate_video.py --case-id img3254_clean22_candidate --dry-run
```

Write a validation report from existing verified artifacts:

```bash
.venv/bin/python scripts/validate_video.py \
  --case-id img3254_clean22_candidate \
  --execute \
  --use-existing-artifacts \
  --output data/reports/img3254_clean22_validation_report.registry_v1.json \
  --force
```

Register a manifest:

```bash
.venv/bin/python scripts/register_test_case.py \
  --manifest validation/test_cases/img3254_clean22.json \
  --registry validation/registry.json \
  --force
```

## Promotion Rule

Only promote a candidate to a numbered test case when the manifest points to clean evidence:

```text
matched_count == expected_total
missing_truth_count == 0
unexpected_observed_count == 0
first_divergence == null
wall_per_source near 1.0
```

Factory2 is promoted as Test Case 1. IMG_3262, IMG_3254, and IMG_2628 are verified candidates, not numbered test cases.

## Active Learning And Teacher Labels

The validation path must not accept teacher/VLM labels as truth. Active-learning evidence and teacher outputs may help build review packets, train future models, and audit failures, but they do not replace the real app proof path.

Allowed advisory artifacts:

```text
validation/schemas/event_evidence.schema.json
validation/schemas/teacher_label.schema.json
validation/schemas/review_label.schema.json
validation/schemas/active_learning_dataset.schema.json
```

Current active-learning entry points:

```bash
.venv/bin/python scripts/extract_event_windows.py --case-id img3254_clean22_candidate --extract-review-frames --output data/reports/active_learning/img3254_event_evidence.v1.json --force
.venv/bin/python scripts/moondream_audit_events.py --evidence data/reports/active_learning/img3254_event_evidence.v1.json --provider dry_run_fixture --output data/reports/active_learning/img3254_moondream_audit.dry_run_v1.json --force
.venv/bin/python scripts/teacher_generate_labels.py --evidence data/reports/active_learning/img3254_event_evidence.v1.json --output data/reports/active_learning/img3254_teacher_labels.dry_run_v1.json --force
.venv/bin/python scripts/check_dataset_poisoning.py --teacher-labels data/reports/active_learning/img3254_teacher_labels.dry_run_v1.json
```

`scripts/validate_video.py` and `scripts/register_test_case.py` reject teacher/VLM artifacts if a manifest tries to use them as `truth.truth_ledger_path`.
