# Teacher Verification Event Loop

Updated: 2026-06-09

## Objective

Produce a self-verifying onboarding loop that turns delayed RTSP/file segments
into station-specific training and audit candidates while the existing
YOLO/event runtime remains the only count authority.

Success means a new station can run in observe-only mode, mine likely placement
events, ask teacher VLMs to verify bounded evidence packets, train/evaluate a
station detector, and pass a blind app-runtime replay gate before live
activation. Teacher labels must never mutate `Runtime Total` or become
validation truth automatically.

## Inputs

- Local stream segment manifests from `scripts/record_stream_segments.py`.
- Local segment video files.
- Optional station calibration artifacts.
- Existing validation registry and verified replay cases.
- Teacher dry-run/fake providers by default.
- Cloud teacher providers only when explicitly approved.
- Oracle/Fable architecture reviews from 2026-06-09 as advisory context.

## State Ledger

Use `tasks/todo.md` as the human-readable ledger. Each tick records:

- objective slice
- files changed
- commands run
- artifact paths
- verifier results
- next state

Long-lived design doctrine lives in this doc and the active-learning docs.
Generated evidence lives under `data/reports/onboarding/` or the local artifact
archive, not in chat.

## Tick

1. Inspect current docs, ledger, source, and latest artifacts.
2. Pick one bounded milestone.
3. Implement only that slice.
4. Run focused unit/CLI/schema tests.
5. Run runtime replay or benchmark checks when the slice affects proof.
6. Use Codex/Fable/Oracle review at architecture or proof boundaries.
7. Record evidence and decide the next state.

## Milestones

| Milestone | Build | Required verifier |
| --- | --- | --- |
| TVL0 | Loop plan and current doctrine | doc index updated; ledger section added |
| TVL1 | High-recall event proposer | pure clustering tests; CLI help; synthetic segment smoke |
| TVL2 | Teacher evidence packet v2 | generated packet manifest has before/during/after, full-frame, crop, and diff assets |
| TVL3 | Teacher verification contract | dry-run/fake teacher tests for assert/refute/unclear outputs; no cloud by default |
| TVL4 | State-diff reconciler | stable before/after samples reconcile event count deltas on known cases |
| TVL5 | Asymmetric fusion and label promotion | bronze/silver gates reject circular validation truth and duplicate events |
| TVL6 | Benchmark gates and ablation | teacher pipeline beats no-teacher baseline on blinded benchmark |
| TVL7 | Factory2 rebenchmark | new evidence/teacher loop graded against hidden Factory2 truth only at final grade |
| TVL8 | Unseen video benchmark | second materially different video runs blind through the same loop |
| TVL9 | RTSP soak | real camera stream proof before live field claims |

## Verifiers

Machine truth first:

```bash
.venv/bin/python -m pytest tests/test_onboarding_event_proposer.py tests/test_onboarding_cli_scripts.py -q
.venv/bin/python -m py_compile app/services/onboarding_event_proposer.py scripts/propose_onboarding_events.py
.venv/bin/python -m pytest tests/test_teacher_evidence_packets.py tests/test_onboarding_cli_scripts.py -q
.venv/bin/python -m py_compile app/services/teacher_evidence_packets.py scripts/build_teacher_evidence_packets.py
.venv/bin/python -m pytest tests/test_teacher_verification_contract.py tests/test_state_diff_reconciler.py tests/test_teacher_fusion.py tests/test_teacher_loop_benchmark.py tests/test_onboarding_cli_scripts.py -q
.venv/bin/python -m py_compile app/services/teacher_verification.py scripts/generate_teacher_verifications.py app/services/state_diff_reconciler.py scripts/reconcile_state_diff.py app/services/teacher_fusion.py scripts/fuse_teacher_verifications.py app/services/teacher_loop_benchmark.py scripts/run_teacher_loop_benchmark.py
```

Runtime proof when artifacts are produced:

```bash
.venv/bin/python scripts/propose_onboarding_events.py \
  --segment-manifest <segment_manifest.json> \
  --output data/reports/onboarding/<station>_event_proposals.json \
  --force

.venv/bin/python scripts/build_teacher_evidence_packets.py \
  --event-proposals data/reports/onboarding/<station>_event_proposals.json \
  --output-dir data/reports/onboarding/<station>_teacher_evidence_packets \
  --force

.venv/bin/python scripts/generate_teacher_verifications.py \
  --packet-manifest data/reports/onboarding/<station>_teacher_evidence_packets/teacher_evidence_manifest.json \
  --output data/reports/onboarding/<station>_teacher_verifications.json \
  --force

.venv/bin/python scripts/reconcile_state_diff.py \
  --packet-manifest data/reports/onboarding/<station>_teacher_evidence_packets/teacher_evidence_manifest.json \
  --teacher-labels data/reports/onboarding/<station>_teacher_verifications.json \
  --output data/reports/onboarding/<station>_state_diff_reconciliation.json \
  --force

.venv/bin/python scripts/fuse_teacher_verifications.py \
  --teacher-labels data/reports/onboarding/<station>_teacher_verifications.json \
  --state-diff data/reports/onboarding/<station>_state_diff_reconciliation.json \
  --silver-dataset data/reports/onboarding/<station>_silver_training_candidates.json \
  --output data/reports/onboarding/<station>_teacher_fusion.json \
  --force

.venv/bin/python scripts/run_teacher_loop_benchmark.py \
  --event-proposals data/reports/onboarding/<station>_event_proposals.json \
  --teacher-labels data/reports/onboarding/<station>_teacher_verifications.json \
  --fusion-report data/reports/onboarding/<station>_teacher_fusion.json \
  --output data/reports/onboarding/<station>_teacher_loop_benchmark.json \
  --force
```

Checkpoint review:

- Run focused Codex review after TVL2, TVL5, and TVL7.
- Ask Oracle/Fable again only when architecture or product truth semantics
  change.

## Budgets

- One tick should touch one milestone.
- Default retry budget is two verifier failures for the same root cause.
- No cloud teacher calls unless Thomas explicitly approves the provider and
  footage privacy mode.
- No live activation without a blind replay gate.
- No model promotion from teacher labels alone.

## Stop Rules

- **Complete:** milestone verifier passes and evidence is recorded.
- **Retry:** verifier fails and the next fix is clear.
- **Escalate:** cloud permission, RTSP credential, product semantics, or count
  authority would change.
- **Rollback:** a change weakens proven Factory2/IMG proof paths and no small
  fix is obvious.
- **Blocked:** the same blocker repeats three times with no useful next action.

## Artifacts

- Event proposal manifests.
- Teacher evidence packet manifests.
- Teacher labels with `validation_truth_eligible=false`.
- Promotion gate reports.
- Training/eval reports.
- Blind replay gate reports.
- Periodic audit dispute/retraining reports.
- Ledger entries in `tasks/todo.md`.

## First Tick

Implement TVL1: a high-recall local event proposer that reads recorded segment
manifests, samples frame-to-frame motion, clusters likely activity bursts, emits
advisory candidate event windows, and also emits stable hard-negative
candidates. It must not call a model, train a model, or alter runtime counts.
