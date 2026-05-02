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
make run-test-case-1
make validate-video CASE_ID=img3254_clean22_candidate
```

## Test Case 1

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Open:

```text
http://127.0.0.1:5173/dashboard
```

Expected result: Runtime Total reaches `23`; comparison artifact is `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json`.

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
