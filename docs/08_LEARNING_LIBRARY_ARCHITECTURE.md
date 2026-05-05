# Learning Library Architecture

Updated: 2026-05-03

## Purpose

Factory Vision must improve from every factory run without confusing diagnostic output, teacher labels, training labels, and validation proof.

The learning library is the productized path for turning videos, failed diagnostics, reviewed events, labels, datasets, detector experiments, and app proof runs into reusable assets. It does not change the live counting authority: Runtime Total still comes only from the configured YOLO/event app path.

## Storage Model

Git remains the brain and index. The local artifact root remains the heavy-artifact warehouse:

```text
/Users/thomas/FactoryVisionArtifacts
```

Repo paths should contain docs, scripts, tests, schemas, small reports, manifests, and indexes:

```text
validation/
  registry.json
  artifact_storage.json
  learning_registry.json
  datasets/
  detectors/
  teachers/
  cloud_permissions/
  schemas/
```

The artifact root should contain heavy or generated assets:

```text
/Users/thomas/FactoryVisionArtifacts/
  videos/raw/
  videos/proxies/
  videos/clips/
  frames/review/
  frames/training/
  evidence/
  teachers/
  reviews/
  labels/gold/
  labels/silver/
  labels/bronze/
  datasets/
  models/
  runs/app/
  promotions/
  embeddings/
  backups/
```

Do not upload factory footage or selected clips to cloud storage unless the customer or Thomas explicitly approves that path.

## Artifact Authority

Use distinct artifact names because each class has a different authority boundary.

| Artifact | Meaning | Validation Truth? | Training Eligible? |
| --- | --- | --- | --- |
| `detector_transfer_screen` | Existing detectors sampled on a candidate video | No | No |
| `runtime_diagnostic_run` / `observed_events` | App attempted with candidate settings | No by itself | No by itself |
| `candidate_windows` / `event_evidence` | Review windows around events, misses, or hard negatives | No | No by itself |
| `teacher_labels` | VLM/frontier/local teacher suggestions | No | Bronze only |
| `review_labels` | Human or reconciler decisions on a review batch | Only when promoted to gold truth | Depends on tier |
| `gold_event_ledger` | Reviewed timestamp truth | Yes | Yes |
| `dataset_manifest` | Locked split with source hashes and label tiers | No proof by itself | Yes if gates pass |
| `model_card` / `train_report` / `eval_report` | Detector experiment metadata and metrics | No proof by itself | N/A |
| `app_proof_run` | Visible real app path at 1.0x with clean truth comparison | Yes | Regression evidence |

Teacher outputs start as `bronze` and `pending`. They cannot be validation truth. Runtime observations are useful evidence, but they cannot become truth without human/reconciled review.

## Lifecycle

Use this sequence for every new or failed factory video:

1. `video_intake`: copy, hash, ffprobe, privacy mode, candidate manifest.
2. `detector_transfer_screen`: sample known detectors and classify transfer viability.
3. `runtime_diagnostic_run`: run plausible app settings only when detector evidence supports it.
4. `candidate_window_mining`: extract event, miss, duplicate, static, and hard-negative windows.
5. `teacher_label_run`: optional local or explicitly approved cloud teacher suggestions.
6. `human_review_batch`: human/VA/reconciler approves, edits, rejects, or marks unclear.
7. `gold_label_set`: reviewed event ledger, boxes, and window labels.
8. `dataset_assembly`: split frames/windows by source event/video with leakage checks.
9. `model_train_run`: train or fine-tune a detector candidate.
10. `model_eval_run`: evaluate on held-out frames/windows/videos.
11. `app_proof_run`: run the real dashboard path at `1.0x`.
12. `model_promotion`: update detector cards/registry only after clean proof.

## Abstention Rule

A blind numeric estimate is not valid when:

- active transferred detectors are all dead or near-dead,
- the only high-recall detector is a broad/static risk detector,
- runtime diagnostics are parameter-sensitive or dominated by dead-track/static fragmentation.

That situation must produce `numeric_prediction_allowed=false` and route the case to the learning library. The output is still useful: the false events become hard negatives, and the true placements become gold positives after review.

## real_factory Treatment

`real_factory.MOV` is a learning case, not a verification success.

Current outcome:

- hidden human total after blind phase: `4`
- failed static-detector diagnostic total: `18`
- active transferred detectors: failed
- `wire_mesh_panel.pt`: static/broad detector risk, `80/80` sampled frames
- registry promotion: not eligible

Next useful work:

1. Build the reviewed 4-event truth ledger.
2. Preserve the `wire_mesh_panel.pt` false events as hard-negative candidates.
3. Assemble reviewed positive/negative training windows.
4. Train a `real_factory`-specific detector.
5. Rerun the real app path and compare against reviewed truth.

## Learning Registry v2

`validation/learning_registry.json` is the registry-first index for learning-library cases. Reports are evidence references only; they are not scraped as source of truth.

Use the recommendation CLI to inspect the current safe next action:

```bash
.venv/bin/python scripts/factory_learn.py recommend --case-id real_factory_candidate --format text
.venv/bin/python scripts/factory_learn.py recommend --case-id factory2 --format json
```

The CLI resolves aliases, checks required evidence/prerequisite artifacts, emits `artifact_warnings[]`, and blocks affected readiness fields when required artifacts are missing. It also fails closed on invalid trust claims, such as `promotion_eligible=true` without `validation_truth_eligible=true`.

Current indexed cases:

- `factory2_test_case_1` alias `factory2`: verified app-proof anchor, promotion eligible, useful as the high-count regression case.
- `real_factory_candidate` alias `real_factory`: diagnostic runtime recovery only, not validation truth, not training eligible, and blocked on reviewed gold truth plus a real_factory placed-and-stayed calibration file.

## Cloud Teacher Policy

Default mode is `offline_local`.

Cloud teacher models are setup accelerators only when there is explicit permission. Record provider, model, prompt version, timestamp, frame hashes, and permission id. Store outputs as bronze suggestions. Do not use cloud teacher output as validation truth or silent runtime authority.

Local/on-prem teacher paths are allowed for review acceleration, but they still produce advisory labels until reviewed.
