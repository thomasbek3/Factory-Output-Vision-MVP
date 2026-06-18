# Day-4 Camera-Only Action-Recognition Counter — Implementation Spec

Status: APPROVED for implementation, 2026-06-13.
Authored by Claude (reviewer). Implementation by Codex (coder).
Branch: `day4-action-recognition` (cut from `day3-wide-net-miner`).
Rollback point: record HEAD of `day3-wide-net-miner` before first change.

## Why (one paragraph)

YOLO object detection is dead for this station: the product is thin wire lattice
that is unboxable from overhead (proven 3 ways — pile is a "noodle bowl", carried
frame merges with the worker, even zoomed). The trained detector scored 0/7 and
0% recall on its own training images. The signal here is NOT an object in a frame
— it is an ACTION over time (carry -> place -> leave), which Codex reads perfectly
(7/7 on the human-verified exam). So we pivot the student from object detection to
**clip action-recognition**: a cheap pixel tripwire proposes candidate windows, a
small video model judges "placement / not", a state machine counts. This is the
Drishti approach, camera-only. No new hardware. Validatable today on existing
footage. The blind 7-placement exam is the only acceptance truth (Drishti has no
public benchmark; we hold ourselves to a higher bar).

## Ground-truth constants (reuse, do not regenerate)

- Station `factory-live-day1`, native 2560x1920, fixed camera.
- Output-zone polygon: `[[0.48,0.56],[1.0,0.56],[1.0,1.0],[0.48,1.0]]`
- Day-1 segments + segment_manifest under
  `.../onboarding/factory_live_day1/recordings/factory-live-day1/`
- Exam clip + 7 gold placements: `.../pipeline_day2_full/exam_clip.mp4`,
  `.../pipeline_day2_full/exam_gold_positives.json` (clip-offset placement secs
  165, 510, 781, 1104, 1475, 1822, 2172). NEVER train on these — exam only.
- Station calibration JSON already exists in the day1 onboarding dir.

## Scope tonight (CODE only — no labels exist yet)

Build and unit-test the full pipeline so that the moment Thomas labels footage
tomorrow, the bake-off runs end to end. Do NOT fabricate labels. Do NOT train on
real data tonight (no labels) — but every component must run on synthetic fixtures
in tests, and the trainers must run a 1-epoch smoke test on a tiny synthetic set.

## Change 1 — Tripwire v2 (`app/services/zone_tripwire.py`, new)

A cheap, no-AI change detector on the output-zone crop. Goal: RECALL — flag every
placement, tolerate many false alarms (the model filters them). Fixes the day-3
miner's 4/7 ceiling (it watched 2fps, quarter-res, single grayscale mean — thin
wire vanished). Requirements:

- Operate on the polygon-cropped zone at FULL native resolution (no downscale
  below the crop's own size).
- Sample at configurable fps, default 10 (day-3 used ~2).
- Change score = MAX over a grid of NxN tiles (default 8x8) of per-tile normalized
  abs-diff, NOT a single whole-zone mean. A thin frame lights up a few tiles even
  when the zone average barely moves. Also expose SSIM-drop and edge-diff
  (Sobel) as alternative per-tile scores behind a `--score-method` flag
  (`tiled_absdiff` default, `tiled_ssim`, `tiled_edge`).
- Two trigger modes, OR'd:
  - `motion_burst`: tile score over `--burst-threshold` (default low, 0.10).
  - `quiet_state_diff`: every `--state-interval` sec (default 3), capture a CALM
    zone snapshot (a frame whose whole-zone motion is below `--calm-threshold`,
    i.e. nobody moving in it); compare consecutive calm snapshots; if their tiled
    diff exceeds `--state-threshold`, emit a candidate centered between them. This
    is the quiet-placement backstop that catches what motion bursts miss.
- Flash rejection: drop a candidate when the change is globally uniform — compute
  `flash_ratio = zone_local_change / full_frame_change`; reject if < `--min-flash-ratio`
  (default 1.5). (Reuse the day-3 flash logic if cleanly importable.)
- Output: list of candidate windows `{center_sec, start_sec, end_sec, trigger_mode,
  peak_tile_score, flash_ratio}`; bracket = center +/- `--bracket-sec` (default 8).
- CLI `scripts/run_zone_tripwire.py`: `--segment-manifest|--video`, `--station-calibration`,
  score/threshold flags, `--out candidates.json`.

## Change 2 — Tripwire recall gate (extend `scripts/validate_miner_recall.py` OR new `scripts/validate_tripwire_recall.py`)

Run Tripwire v2 over the exam hour, score candidate recall vs the 7 gold
placements (caught = a candidate center within `--match-tolerance-sec`, default 20,
of a gold placement). Print per-gold caught/missed + nearest delta. Exit 0 (PASS)
only if >= 6/7 caught; else exit 1. This gate MUST pass before any teacher spend
or training. (Day-3's equivalent scored 4/7 — that is the bar to beat.)

## Change 3 — Clip extractor (`app/services/clip_dataset.py`, new)

Given candidate windows + the source video, materialize one training/inference
SAMPLE per candidate:

- Decode the zone-cropped clip at `--clip-fps` (default 6) for the bracket window.
- Produce two tensor encodings behind a `--encoding` flag so the bake-off can feed
  every model from one cache:
  - `stack3`: 3 frames (before / mid / after) stacked → for the 2D-CNN baseline.
  - `clip`: T frames (default 16) uniformly sampled → for video models.
  - `flow`: precomputed optical flow (Farneback, cv2) for the clip → for the
    two-stream variant.
- Persist as `.npz` + a manifest row `{candidate_id, source, center_sec, paths,
  label?}`. Label is null until a teacher/human fills it.
- Deterministic, resumable, content-hashed filenames.

## Change 4 — Labeling harness (`scripts/label_clips.py`, new)

Turn candidate clips into labeled samples. Two interchangeable label sources:

- `--labeler codex`: render the clip as a contact sheet (the proven approach:
  native frames, before/during/after), call `codex exec` read-only with the
  placement-judge prompt, parse `assert/refute` + confidence. Support
  `--votes N` (default 1; 3 = 2-of-3 majority, Drishti's discipline) for the
  ground-truth set.
- `--labeler human`: ingest a Thomas timestamp list (`--times` seconds-from-source
  or a CSV), mark the matching candidates positive, the rest negative; emit an
  HTML/contact-sheet review sheet so a human can audit/flip any.
- Writes `label` into the clip manifest. Never writes labels for the exam window.

## Change 5 — Student bake-off (`app/services/clip_models.py` + `scripts/train_clip_student.py`)

Model-agnostic trainer over the labeled clip manifest. Three architectures behind
`--arch`:

- `stack3_mobilenet`: torchvision MobileNetV3-small, first conv adapted to 9-channel
  (3 stacked RGB), ImageNet-pretrained backbone. The weak baseline.
- `video_x3d` (front-runner-A) and `video_vmae` (front-runner-B): a small
  pretrained video classifier. Use `pytorchvideo` X3D-XS and a VideoMAE-small from
  `transformers`/`timm` if available; if a dependency is missing, SKIP that arch
  with a clear logged reason rather than failing the run.
- `twostream`: `stack3_mobilenet` over RGB + a second MobileNet branch over the
  `flow` encoding, late-fused. Tests whether the motion channel cracks the subtle
  cases.

Requirements:

- Validation split BY TIME BLOCK / by day, never random (fixed camera → random
  split leaks). 
- Heavy augmentation suited to a fixed camera (temporal jitter, small photometric;
  NO geometric flips that move the zone).
- Freeze most of the backbone; train the head + last block (few-label regime).
- Output per-arch metrics + a saved model. `scripts/train_clip_student.py --arch all`
  trains every available arch and writes a comparison table.
- 1-epoch synthetic smoke test must pass in CI for each available arch.

## Change 6 — Blind exam scorer (`scripts/run_clip_exam.py`)

Reuse the existing exam concept against the 7 gold placements, but for the clip
student: run the tripwire over the exam clip, judge every candidate with a trained
student, debounce (Change 7), and score matched / missed / false-count vs the
ledger. Output per-model `{matched, missed, false_counts, passed}`. PASS = 7/7
matched AND 0 false counts. This is THE acceptance gate and the bake-off ranking.

## Change 7 — Counting state machine (`app/services/placement_counter.py`, new)

Live counting from a stream of per-window student verdicts: a count fires on a
quiet -> placement -> quiet transition in the zone; merge verdicts within
`--debounce-sec` (default 25) so one slow placement counts once. Pure logic, unit
tested, no model.

## Tests (all green: `.venv/bin/python -m pytest tests/ -q`)

- Tripwire: synthetic zone where a thin bright bar appears in 3 tiles scores high
  on `tiled_absdiff` but ~0 on whole-zone mean; quiet_state_diff fires across a
  calm-before/calm-after pair; flash (uniform brighten) is rejected.
- Recall gate: caught/missed logic at the tolerance boundary; PASS at 6/7, FAIL 5/7.
- Clip extractor: stack3/clip/flow shapes correct; deterministic hashing; resumable.
- Labeling: codex stub (monkeypatched) parses assert/refute; 3-vote majority; human
  timestamp ingestion maps to the right candidates; exam window never labeled.
- Models: each available arch does a 1-epoch synthetic smoke train + forward.
- Counter: debounce merges a double-trigger into one; quiet->placement->quiet logic.
- Exam scorer: synthetic verdicts → matched/missed/false math correct.

## Non-goals tonight

- No real training (no labels yet). No live RTSP runtime wiring. No dashboard. No
  sensors. No touching recorder/manifest code. Do NOT inject the 7 gold positives
  into any training set, ever.

## Acceptance checklist

1. `pytest` green, including 1-epoch synthetic smoke per available arch.
2. Tripwire recall gate runs and prints an N/7 verdict on the exam hour.
3. `scripts/label_clips.py --labeler codex` runs end-to-end on 3 real candidate
   clips (judging only, outside the exam window).
4. `scripts/train_clip_student.py --arch all` runs on a tiny synthetic labeled set
   and writes a comparison table (skipping any arch whose deps are absent, logged).
5. Commits on `day4-action-recognition` only — surgical, no drive-by edits.
