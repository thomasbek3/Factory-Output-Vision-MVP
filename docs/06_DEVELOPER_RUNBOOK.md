# Developer Runbook

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

The existing `.venv` is normally already present on this machine.

## Common Commands

```bash
make test-backend
make lint
make build
make docs-check
make hygiene
make check-trackb-env
make run-test-case-1
make validate-video CASE_ID=img3254_clean22_candidate
make benchmark-onboarding
```

`make docs-check` runs the lightweight repository hygiene check. `make check-trackb-env` checks whether the optional Track B model packages are importable. `make hygiene` runs docs-check, backend tests, frontend lint, and frontend build.

## Test Case 1

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Open:

```text
http://127.0.0.1:5173/dashboard
```

Expected result: Runtime Total reaches `23`; comparison artifact is `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json`.

## Track B: Overhead Wire-Frame Action Recognition

Track B is the current live-station evaluation lane. It is for the overhead
wire-frame station where YOLO cannot box the product. The workflow is:

```text
zone tripwire -> candidate clips -> teacher/human labels -> clip student -> blind exam
```

Install the optional ML packages before training or running VideoMAE/X3D model
paths:

```bash
.venv/bin/pip install -r requirements-ml.txt
make check-trackb-env
```

The held-out answer key lives under `validation/exam/`. Never train on those
seven placements; they are the blind exam, like keeping the answer sheet sealed
until grading.

Tripwire candidate mining:

```bash
.venv/bin/python scripts/run_zone_tripwire.py \
  --video /path/to/video.mp4 \
  --station-calibration data/calibration/<station>.json \
  --trigger person_presence \
  --sample-fps 2 \
  --score-method tiled_absdiff \
  --out data/reports/trackb_candidates.json
```

Important flags: `--segment-manifest` can replace `--video`; `--trigger` is
`person_presence` or `pixel`; tuning knobs include `--grid-size`,
`--burst-threshold`, `--state-interval`, `--calm-threshold`,
`--state-threshold`, `--min-flash-ratio`, `--bracket-sec`,
`--include-motion-burst`, `--person-conf`, `--person-model`,
`--presence-gap-sec`, `--episode-max-sec`, `--trigger-zone-margin`, and
`--episode-pad-sec`.

Tripwire recall check:

```bash
.venv/bin/python scripts/validate_tripwire_recall.py \
  --tripwire-candidates data/reports/trackb_candidates.json \
  --gold-positives validation/exam/exam_gold_positives.json \
  --match-tolerance-sec 10 \
  --out data/reports/trackb_tripwire_recall.json
```

Instead of `--tripwire-candidates`, this command can run directly from
`--video` or `--segment-manifest`. It also accepts `--pm-gold-positives` and
`--gold-wall-date` for plain wall-clock label files, plus the same tripwire
tuning flags used by `run_zone_tripwire.py`.

Clip extraction:

```bash
.venv/bin/python scripts/extract_clip_dataset.py \
  --candidates data/reports/trackb_candidates.json \
  --video /path/to/video.mp4 \
  --station-calibration data/calibration/<station>.json \
  --encoding all \
  --clip-fps 4 \
  --clip-frames 24 \
  --out-dir data/trackb/clips \
  --manifest-out data/trackb/clip_manifest.json \
  --force
```

`--encoding` is `stack3`, `clip`, `flow`, or `all`. Use `--video` when the
candidates file does not carry source paths.

Clip labeling:

```bash
.venv/bin/python scripts/label_clips.py \
  --manifest data/trackb/clip_manifest.json \
  --out data/trackb/labeled_clips.json \
  --labeler human \
  --times data/trackb/human_times.csv \
  --match-tolerance-sec 10 \
  --review-html data/trackb/review.html
```

`--labeler` is `human` or `codex`; `--votes` supports multi-vote teacher passes.

Student training:

```bash
.venv/bin/python scripts/train_clip_student.py \
  --manifest data/trackb/labeled_clips.json \
  --arch all \
  --out-dir models/trackb_clip_student \
  --epochs 10 \
  --batch-size 4 \
  --device cpu
```

`--arch` is `stack3_mobilenet`, `video_x3d`, `video_vmae`, `twostream`, or
`all`. `--pretrained` tries pretrained backbones where available, and
`--synthetic-smoke` creates a tiny smoke-test manifest without a real dataset.

Blind exam:

```bash
.venv/bin/python scripts/run_clip_exam.py \
  --video /path/to/exam_clip.mp4 \
  --gold-positives validation/exam/exam_gold_positives.json \
  --station-calibration data/calibration/<station>.json \
  --model models/trackb_clip_student/model.pt \
  --arch video_vmae \
  --clip-cache-dir data/trackb/exam_clip_cache \
  --write-candidates data/reports/trackb_exam_candidates.json \
  --debounce-sec 30 \
  --match-tolerance-sec 10 \
  --out data/reports/trackb_clip_exam.json
```

If candidates were already mined, pass `--candidates` instead of
`--write-candidates`. The exam report must match all seven held-out placements
with zero false counts before Track B can be promoted.

## New Video Candidate

The next candidate should get faster because the first pass is now scripted.

```bash
.venv/bin/python scripts/bootstrap_video_candidate.py \
  --case-id new_candidate \
  --video data/videos/from-pc/NEW_VIDEO.MOV \
  --expected-total 25 \
  --baseline-case-id img2628_candidate \
  --preview \
  --force
```

This writes the fingerprint, provisional human-total artifact, timestamp template, and candidate manifest. The total is only a target for diagnostics; it is not proof.

Fast-path gates:

1. Run detector transfer screening before a long app run. If sampled recall is near zero, stop tuning old settings and build a small video-specific detector.
2. Run accelerated real-app diagnostics first. Do not spend 30 minutes on visible `1.0x` until the accelerated path is plausible.
3. If the total matches but event timing does not, build a focused dispute packet around mismatches instead of broad manual review.
4. Run the visible dashboard path at `1.0x` only after the diagnostic path is plausible.
5. Register the manifest only after reviewed timestamp truth and app-vs-truth are clean.

Detector transfer screen:

```bash
.venv/bin/python scripts/screen_detector_transfer.py \
  --video data/videos/from-pc/NEW_VIDEO.MOV \
  --model models/img2628_worksheet_accept_event_diag_v1.pt \
  --model models/img3254_active_panel_v4_yolov8n.pt \
  --model models/img3262_active_panel_v2.pt \
  --sample-count 80 \
  --confidence 0.25 \
  --output data/reports/new_candidate_detector_transfer_screen.v1.json \
  --force
```

Validation commands still use the manifest:

```bash
.venv/bin/python scripts/validate_video.py --case-id <case-id> --dry-run
.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/<case-id>.json --force
```

## AI-Only Onboarding Benchmark

Use this to test the blind onboarding artifact flow on prerecorded footage:

```bash
make benchmark-onboarding
```

For a specific video:

```bash
make benchmark-onboarding \
  ONBOARDING_VIDEO=/path/to/video.mp4 \
  STATION_ID=station-test-001 \
  ONBOARDING_MINUTES=20
```

The default provider is `dry_run_fixture`; it should not claim success. See `docs/12_AI_ONBOARDING_BENCHMARK.md` before adding real VLM/teacher providers.

## Artifact Storage

Heavy artifacts are local-first. The current local artifact root is:

```text
/Users/thomas/FactoryVisionArtifacts
```

Use it as the durable local warehouse for raw videos, large frame folders, model libraries, reports, and embedding/search indexes. Keep repo `data/` and `models/` paths working as the local script/app cache.

For a new raw video:

```bash
mkdir -p /Users/thomas/FactoryVisionArtifacts/videos/raw
cp -c -n data/videos/from-pc/NEW_VIDEO.MOV /Users/thomas/FactoryVisionArtifacts/videos/raw/
shasum -a 256 data/videos/from-pc/NEW_VIDEO.MOV /Users/thomas/FactoryVisionArtifacts/videos/raw/NEW_VIDEO.MOV
```

Then record the artifact path and hash in the test-case manifest or `validation/artifact_storage.json`. Do not commit raw factory videos to normal Git and do not upload them to cloud storage without explicit permission.

## Guardrails

- Do not delete historical artifacts during cleanup.
- Do not present timestamp replay, deterministic reveal, or offline retrospective counting as app proof.
- Do not claim RTSP/Reolink field validation until it has a real live-camera manifest and clean comparison.
- Do not move research scripts without updating tests/imports in the same change.
- Do not promote new detectors, hardware, or vendor workflows without an ADR and validation-registry proof.
- Do not upload factory footage, labels, or model artifacts without explicit permission.
