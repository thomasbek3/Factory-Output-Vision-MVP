# Autonomous Onboarding Rehearsal

Updated: 2026-07-04

This document defines the autonomous station-onboarding rehearsal: an offline, end-to-end proof
that raw station footage can become a gate-passing per-station model with zero human box labeling.
It composes the existing teacher-verification loop (docs/14) with three new lanes: real
subscription-CLI teachers, an automatic box-labeling lane, and a leakage-safe holdout gate.

## Objective

Measure, on the four gold validation stations, whether the pipeline

```text
raw footage (train portion)
  -> recorder segments
  -> motion event proposals (+ stable hard negatives)
  -> teacher evidence packets
  -> REAL teacher verification (claude_cli / codex_cli)
  -> state-diff reconciliation
  -> asymmetric fusion -> silver event candidates
  -> diff-box auto labels -> deterministic label review gate
  -> YOLO dataset assembly -> per-station training
  -> blind replay gate on the HELD-OUT footage tail
```

produces a model that counts the holdout correctly with the standard parameter set.

**Success criterion: >=3 of 4 stations pass the blind replay gate with zero human labels.**
The human-built baseline models (validation/registry.json) are the comparison reference (4/4).

## Real teachers (subscription CLIs)

- `claude_cli` drives `claude -p` headless (Read-tool image viewing); `codex_cli` drives
  `codex exec` with attached images and a stdin prompt. Both are registered in
  `app/services/teacher_verification.py` and implemented in `app/services/cloud_teacher_providers.py`.
- Both refuse to construct without `--allow-cloud` (frames leave the machine to Anthropic/OpenAI;
  subscription billing does not change the privacy boundary).
- Labels remain bronze/pending, never validation truth (`teacher-verification-cli-v1` prompt
  contract, asymmetric high-recall instructions; the conservative check is the state-diff
  reconciler downstream).
- Batching: ~4 packets per CLI invocation; parse/transport failures split-retry and degrade to
  `unclear`, never crash a run. `--resume` reuses non-error labels from a prior output.
- Grading is diagnostic-only: `scripts/grade_teacher_labels_vs_truth.py` scores asserts against a
  reviewed human truth ledger (`factory-vision-teacher-grade-vs-truth-v1`). Segment-relative
  timestamps map onto the source timeline via the segment manifest, sorted by segment file index
  (NOT wall timestamps, which are unordered for faster-than-realtime file replays).
- Factory2 baseline grades (full 60-packet set, 5s tolerance):
  - `codex_cli` v1: precision 0.909, recall 0.870, mean timing error 0.78s.
  - `claude_cli` v1: see `teacher_grade.claude_cli_v1.json` in the Factory2 onboarding artifacts.

## Auto-box lane

`app/services/box_autolabeler.py` (`auto-box-label-manifest-v1`):

- Default backend `diff_box` (zero new dependencies): median composites over a few seconds on
  each side of the event erase the moving worker; their diff -> Otsu threshold -> morphology ->
  largest contour locates the LANDING region; global-motion guard (>40% changed pixels) skips
  the event. Labeled frames are the PLACEMENT-ACT frames: samples around the event center whose
  landing patch differs from both the before-state and the settled after-state. The settled part
  is never labeled — it is pixel-identical to the unlabeled stack around it, which poisons
  training (observed empirically: a settled-part dataset trains to zero confidence). This
  matches the verified runtime semantic (`panel_in_transit`).
- Optional backend `yolo_world` (open-vocabulary, ultralytics) behind explicit
  `--yolo-world-model`/`--allow-model-download` flags.
- Output rows are shape-compatible with the existing deterministic review gate
  (`scripts/review_labels_ai.py` -> `label-quality-reviewed-v1`) and assembler
  (`scripts/assemble_active_panel_dataset.py`); `metadata.split` carries the deterministic
  event-granular train/val split (all frames of one event share a split).
- Hard negatives: `scripts/export_onboarding_stable_negatives.py` turns stable low-motion
  proposals into `factory-hard-negative-export-v1` empty-label images.
- A teacher crop-verification stage (accept/reject each proposed box crop) is designed but not
  built; it is the next lever if box quality ever blocks the gate.

## Standard event parameters (no per-station tuning)

`app/services/holdout_split.py:STANDARD_EVENT_PARAMS` — fixed for every auto-onboarded station:

| param | value |
| --- | --- |
| demo_count_mode | live_reader_snapshot |
| counting_mode | event_based |
| processing_fps / reader_fps | 10 |
| runtime_calibration_path | auto-derived zones (see below), still zero human input |
| yolo_confidence | 0.25 |
| event_track_max_age | 30 |
| event_track_min_frames | 8 |
| event_detection_cluster_distance | 150.0 |

Runtime calibration zones are auto-derived per station by
`app/services/auto_station_calibration.py` from train-portion evidence only: the output zone is
the union of teacher-verified landing boxes (plus margin) and the source zone is the busiest
residual-motion region outside it. This mirrors the verified factory2 baseline, where
output-zone gating in `RuntimeEventCounter` is what suppresses worker-transit false events.

A station failing the gate with these params is a finding about the pipeline, not something to
fix by hand-tuning that station. The four gold baselines were each hand-tuned; that asymmetry is
part of what the rehearsal measures.

## Holdout split and leakage rule

`scripts/build_holdout_case.py` cuts each source video at a keyframe near the 70% mark
(stream-copy, exact alignment), guarantees >=3 truth events in the holdout tail (walking the
split earlier when needed), never splits within 5s of a truth event, derives a shifted/renumbered
holdout truth ledger (`derived-holdout-human-truth-ledger-v1`, passes the validation truth
guard), and authors a derived case manifest (`factory-vision-video-manifest-v1`) pointing at the
future auto-trained model so the unmodified blind replay gate can consume it.

Leakage rule, enforced structurally and by a unit-tested assertion
(`app/services/onboarding_rehearsal.py:assert_no_truth_leakage`):

- Truth ledgers are touched ONLY by: split selection (timestamps only, recorded as
  `truth_timestamp_touch: split_selection_only`), the gate compare, and the post-gate diagnostic
  teacher grading.
- Every other stage (segments through training) sees only the train clip and may not receive a
  ledger path in its command.

## Playback-speed policy

Rehearsal gate runs default to speed-8 (precedent: the 2026-06-09 Factory2 smoke gate). The
scoreboard records `playback_speed` and measured `wall_per_source` per gate run and carries
`promotion_claim: false`. Registry promotion proof still requires 1.0x per docs/00; a passing
rehearsal station can be re-run at 1.0x before any product claim.

## Running it

```bash
# full 4-station rehearsal (sequential; hours, dominated by training + gate replay)
make rehearse-autonomous-onboarding TEACHER_PROVIDER=codex_cli

# single station
.venv/bin/python scripts/run_autonomous_onboarding_rehearsal.py \
  --work-root /Users/thomas/FactoryVisionArtifacts/rehearsal \
  --output data/reports/onboarding/autonomous_onboarding_rehearsal.json \
  --stations factory2_auto --teacher-provider codex_cli --allow-cloud --force

# teacher bake-off pieces
make generate-teacher-verifications-cloud TEACHER_PROVIDER=claude_cli
make grade-teacher-labels
```

Stages are idempotent: each stage is skipped when its output artifact exists; `--force-stage
<name>` re-runs one stage. Stations run sequentially (ports 8093/5175 for gate runs). Training
uses `yolov8n.pt` (present at repo root) on MPS with automatic CPU retry.

The scoreboard report (`factory-vision-autonomous-onboarding-rehearsal-v1`) carries per station:
stage statuses, teacher fusion/box/dataset summaries, training status plus numeric train gates
(matched-positive ratio >= 0.8, hard-negative false positives == 0), holdout split info, gate
result with playback speed, the human-baseline proof summary, and diagnostic teacher grades
(`metric_provenance: diagnostic_only_ran_after_gate_never_an_input`).

## Claim boundary

- Live `Runtime Total` authority stays with the configured app runtime: Track A
  YOLO/event counting for boxable products, or Track B clip-student counting
  after the blind exam gate. Nothing here mutates it.
- Teacher labels, silver candidates, auto boxes, and trained models are never validation truth.
- A passing rehearsal station is evidence the autonomous onboarding pipeline works on recorded
  footage; it is not a live RTSP field claim (that remains TVL9) and not registry promotion.

## Known environment note

`requirements.txt` pins `ultralytics==8.3.26` while the active `.venv` has 8.4.60 installed (the
yolo_world backend relies on the installed version). Reconciling the pin is a separate decision;
do not silently change it.
