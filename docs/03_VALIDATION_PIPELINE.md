# Validation Pipeline

This is the productized path for adding or rechecking a factory video.

## Goal

Each video candidate should end with a manifest, truth ledger, observed app events, app-vs-truth comparison, pacing evidence, and a final validation report. A clean final total with wrong timing is not done.

## Inputs

- Source video copied into the repo, usually under `demo/`.
- Video SHA-256 and ffprobe metadata.
- Reviewed human truth rule and timestamped truth ledger.
- Model/settings manifest.
- Real app launch settings.

## Stages

1. Register or update the video manifest.
2. Fingerprint the video with SHA-256.
3. Probe duration, codec, resolution, and frame rate.
4. Generate preview/review sheets.
5. Lock the truth rule before final proof.
6. Build a timestamped human truth ledger.
7. Launch the real app stack.
8. Open the dashboard and click `Start monitoring`.
9. Capture backend observed events.
10. Compare observed events to the truth ledger.
11. Measure wall/source pacing.
12. Write a final validation report.
13. Update `validation/registry.json`.

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

Factory2 is promoted as Test Case 1. IMG_3262 and IMG_3254 are verified candidates, not numbered test cases.
