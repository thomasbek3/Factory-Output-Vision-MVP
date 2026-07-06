# Factory Vision — Agent Guide

This file provides repo-local guidance for AI coding assistants working in this repository. Keep it short: route durable doctrine to `docs/` and founder-brain/Obsidian rather than duplicating it here.

## Communication Rule (Always)

When explaining output, results, or concepts to Thomas, always include a plain-English explanation using non-technical metaphors a layman can understand. Technical detail is fine, but it must come WITH the layman version, not instead of it. Example: don't just say "teacher precision 0.91 / recall 0.87" — say "out of every 10 things the teacher flagged, 9 were real (precision), and it caught about 9 of every 10 real events (recall)."

## Current Source Of Truth

Start with the concise current docs before relying on older task logs or research notes:

- `docs/00_CURRENT_STATE.md`
- `DESIGN.md` — locked UI design system (mandatory for ALL frontend/UI work)
- `docs/01_PRODUCT_SPEC.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_VALIDATION_PIPELINE.md`
- `docs/04_TEST_CASE_REGISTRY.md`
- `docs/06_DEVELOPER_RUNBOOK.md`
- `docs/06_AI_ONLY_ACTIVE_LEARNING_PIPELINE.md`
- `docs/07_ARTIFACT_STORAGE.md`
- `docs/08_LEARNING_LIBRARY_ARCHITECTURE.md`
- `docs/09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md`
- `docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md`
- `docs/11_RELEASE_AND_VALIDATION_CHECKLIST.md`
- `docs/12_AI_ONBOARDING_BENCHMARK.md`
- `docs/13_FACTORY_ONBOARDING_AUTOPILOT_LOOP.md`
- `docs/14_TEACHER_VERIFICATION_EVENT_LOOP.md`
- `docs/15_AUTONOMOUS_ONBOARDING_REHEARSAL.md`
- `docs/decisions/`
- `docs/KNOWN_LIMITATIONS.md`
- `validation/registry.json`
- `validation/learning_registry.json`

## What This Is

Factory Vision Output Counter — a plug-and-play factory appliance that counts completed output events from a Reolink camera on an Ubuntu edge PC. It now has two validated doctrine tracks: Track A uses YOLO detection for boxable products in the live app runtime, while Track B uses a zone tripwire plus clip-judge action recognition for the unboxable overhead wire-frame station, per `docs/decisions/0004-pivot-from-yolo-to-clip-action-recognition.md`. Runs fully offline on LAN. No cloud, no Docker, no YAML. Setup must complete in <15 minutes via a web wizard.

## Current Context Routing

This file is a routing layer, not the project brain. Before changing behavior or making proof claims:

1. Read `docs/00_CURRENT_STATE.md` for current validated cases, claim boundaries, and non-negotiables.
2. Read the relevant canonical doc from the list above.
3. For durable product doctrine/research history, consult founder-brain / Obsidian Factory Vision pages.
4. For implementation truth, inspect the live code, validation registry, reports, tests, and logs.

Do not rely on older task logs, archived docs, chat memory, or stale AGENTS prose when a current doc or artifact exists.

`CLAUDE.md` is intentionally only a pointer to this file. Keep all durable agent guidance here, not duplicated across assistant-specific files.

## Critical Claim Boundary

Current app evidence proves file-backed live counting at real-time speed for promoted/verified cases listed in `docs/00_CURRENT_STATE.md`. It does **not** prove live Reolink/RTSP field operation until the same runtime path is validated on an actual live camera stream.

Factory Vision project doctrine belongs in Obsidian/project docs, not Hermes always-loaded memory. This `AGENTS.md` should point agents to the right sources and commands only.

## Data Locations (Mac mini)

The Mac mini's internal disk is nearly full (~3.5GB free); never write heavy artifacts to it.
Everything heavy lives on the attached Crucial X9 Pro SSD (1.8TB):

- Repo working tree (and therefore all repo-relative `data/`, `models/`, `runs/` writes):
  `/Volumes/Crucial X9 Pro For Mac/MacBook-space-offload/2026-05-16/Factory-Output-Vision-MVP/`
- Durable artifact root (raw videos, onboarding runs, rehearsal work dirs, recordings):
  `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/`
- `~/FactoryVisionArtifacts` is a SYMLINK to that SSD artifact root (verified 2026-06-10), so
  paths through the home directory also land on the SSD.
- Live factory day-1 assets: `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding/factory_live_day1/`
- Only tiny helpers may live internal: `~/Library/LaunchAgents/com.factoryvision.record-day1.plist` and `/tmp` scratch (clean after use).

## Learning Library Routing

For failed runs, diagnostic recoveries, training candidates, and artifact trust boundaries, use the learning registry before making recommendations:

```bash
.venv/bin/python scripts/factory_learn.py recommend --case-id real_factory_candidate --format text
.venv/bin/python scripts/factory_learn.py recommend --case-id factory2 --format json
```

`factory2_test_case_1` alias `factory2` is the verified high-count app-proof anchor. `real_factory_candidate` alias `real_factory` is diagnostic-recovered only; it is not validation truth, not training eligible, and not registry-promotion eligible until reviewed gold truth, calibration, and clean app-vs-truth proof exist.

## Commands

### Repo-Level Checks

```bash
make docs-check
make test-backend
make test-frontend
make hygiene
```

Use `make hygiene` before a serious PR or release candidate.

### Backend (Python / FastAPI)

```bash
# Install dependencies (use the .venv already present)
pip install -r requirements.txt

# Run the backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080

# Run in demo mode (uses demo/demo.mp4 or demo/demo_counter.mp4)
FC_DEMO_MODE=1 FC_DEMO_VIDEO_PATH=demo/demo_counter.mp4 python -m uvicorn app.main:app --host 127.0.0.1 --port 8080

# Run the verified Factory2 real-time demo backend
.venv/bin/python scripts/start_factory2_demo_app.py --port 8091

# Run verified Factory2 backend + frontend dev stack
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173

# Run backend tests (pytest, from repo root)
python -m pytest tests/

# Run a single test
python -m pytest tests/test_api_smoke.py
```

### Frontend (React + TypeScript + Vite)

```bash
cd frontend

# Install deps
npm install

# Dev server (proxies /api and /ws to backend on :8080)
npm run dev

# Build for production (output to frontend/dist, served by FastAPI)
npm run build

# Lint
npm run lint

# E2E tests (Playwright — builds frontend, starts backend in demo mode, runs against :8080)
npm run test:e2e

# E2E headed (visible browser)
npm run test:e2e:headed
```

## Architecture

**Backend** (`app/`): FastAPI application with SQLite persistence. `app/main.py` creates the app with lifespan that initializes DB, `VideoRuntime`, and `VisionWorker`.

- `app/api/routes.py` — REST endpoints under `/api` (status, config, control, snapshot, calibration, support bundle, demo management)
- `app/api/ws_routes.py` — WebSocket `/ws/metrics` pushing 1 msg/sec
- `app/api/schemas.py` — Pydantic request/response models
- `app/web/routes.py` — Serves the React SPA from `frontend/dist`; legacy URL redirects
- `app/workers/vision_worker.py` — Background thread running the vision pipeline: frame reading → ROI masking → YOLO detection → person exclusion (class 0 filtered) → centroid tracking → new-object counting in output zone → count accumulation → stop/drop anomaly detection. Model-agnostic: loads whatever .pt is at FC_YOLO_MODEL_PATH
- `app/services/video_runtime.py` — Manages camera/demo video source lifecycle, reconnect with exponential backoff
- `app/services/frame_reader.py` — OpenCV frame reading (RTSP or file)
- `app/services/counting.py` — Count accumulator, centroid tracker, YOLO object detector, new-track counting logic. Excludes person class (class 0) from all counts
- `app/services/zone_tripwire.py` — Track B high-recall output-zone change trigger for candidate placement clips
- `app/services/clip_dataset.py` — Track B candidate clip extraction and manifest writing for teacher/student training
- `app/services/clip_models.py` — Track B clip-student model training, architecture selection, and inference helpers
- `app/services/placement_counter.py` — Track B debounced placement-count state machine fed by clip verdicts
- `app/services/person_detector.py` — Optional YOLOv8 person detection (operator zone / person-ignore pixel masking). NOTE: should be disabled when using custom-trained models (custom models already exclude persons; pixel masking blacks out parts held by workers)
- `app/services/camera_probe.py` — ffprobe-based RTSP stream validation
- `app/services/video_source.py` — RTSP URL builder for Reolink cameras
- `app/db/` — SQLite repos: `database.py` (init), `config_repo.py`, `count_repo.py`, `event_repo.py`, `health_repo.py`
- `app/core/settings.py` — All config via `FC_*` environment variables (no .env file parsing, just `os.getenv`)
- `app/core/logging.py` — Structured logging setup

**Track B CLIs** (`scripts/`):

- `run_zone_tripwire.py` — mine candidate moments from output-zone pixel changes
- `validate_tripwire_recall.py` — prove tripwire recall against reviewed placement times
- `extract_clip_dataset.py` — crop before/during/after candidate clips for labeling and training
- `label_clips.py` — collect human/Codex teacher labels without touching held-out exam clips
- `train_clip_student.py` — train the small live clip model from labeled clips
- `run_clip_exam.py` — run the blind exam gate for Track B promotion

**Frontend** (`frontend/src/`): React 19 + React Router + TypeScript + Vite

> **DESIGN RULE (mandatory):** any frontend/UI work — new screens, components, dashboards, mockups, or image-engine render briefs — MUST follow the locked design system in [`DESIGN.md`](DESIGN.md) (repo root). Reference render: `docs/design/fv-live-a-approved.png` (owner-approved 2026-07-05). Map its color/type tokens 1:1; do not invent palettes, typefaces, brand names, or layout patterns outside it. If a requested change conflicts with DESIGN.md, flag it to the owner instead of improvising.

- `features/wizard/` — Multi-step setup wizard (camera config, ROI drawing, calibration)
- `features/dashboard/` — Live monitoring dashboard (status light, counts, rolling rate, events)
- `features/troubleshooting/` — Diagnostics with debug views, demo playback lab, demo upload
- `shared/api/` — API client functions
- `shared/components/` — Reusable UI components

**Data flow**: VisionWorker thread reads frames → applies ROI mask (output zone) → runs YOLO inference (custom or COCO model) → filters out person detections (class 0) → centroid tracking of remaining objects → counts unique objects appearing in and exiting output zone → updates in-memory state → WebSocket broadcasts metrics to dashboard every second. Config and events are persisted to SQLite.

**Training data directories** (gitignored):
- `datasets/` — Downloaded Roboflow datasets in YOLOv8 format
- `training_runs/` — Ultralytics training output (weights, metrics, plots)

## Key Configuration (Environment Variables)

All settings are `FC_*` env vars defined in `app/core/settings.py`. Key ones:

- `FC_DEMO_MODE` / `FC_DEMO_VIDEO_PATH` — Run with video file instead of camera
- `FC_DB_PATH` — SQLite database location (default: `./data/factory_counter.db`)
- `FC_PROCESSING_FPS` — Vision pipeline FPS cap (default: 10)
- `FC_READER_FPS` — Frame reader FPS (default: 12)
- `FC_PERSON_DETECT_ENABLED` / `FC_PERSON_IGNORE_ENABLED` — Toggle YOLOv8 person detection features. Disable person-ignore pixel masking when using custom-trained models
- `FC_YOLO_MODEL_PATH` — Path to YOLO .pt model file. Default is yolov8n.pt (COCO 80-class). Set to a custom-trained model for per-customer part detection (see `docs/CUSTOM_MODEL_TRAINING.md`). Person class (class 0) is always excluded from counting regardless of model
- `FC_COUNTING_MODE` — `track_based` (default) or `event_based`. Event-based mode uses detection clustering for transit-style counting

## Testing

Backend tests use `FastAPI.TestClient` via `tests/helpers.py:app_client()` context manager, which creates an isolated temp dir with its own DB and env vars. Tests import `create_app` fresh each time.

E2E tests use Playwright (`frontend/e2e/`), auto-starting the backend in demo mode.

## Important Constraints

- v1.0 is camera-only. Beam/serial/v1.5 features are deferred until after factory pilot.
- Do not rewrite the current runtime around a new vendor stack.
- CPU-only inference (no CUDA GPU), capped at 10 FPS processing. Training also CPU-only for now.
- No counting path may be promoted without passing a blind human-verified exam. (This rule is what killed both the pixel-blob counter and YOLO-on-wire for the live station — see ADR `0004-pivot-from-yolo-to-clip-action-recognition.md`.)
- Custom YOLO model training per customer is a core part of the product, not an afterthought. Most factory parts are not in COCO.
- FastAPI serves the React build from `frontend/dist` — if missing, returns 503.
- The `build/windows-installer/` directory contains a snapshot of the app payload for the Windows installer EXE at `dist/windows-installer/`. It is a copy, not the source of truth.
- `docs/ARCHIVED_DONOTREAD/` contains superseded specs — ignore them.
- Authoritative specs start with `docs/00_CURRENT_STATE.md`, then the numbered docs in `docs/README.md`, then `docs/decisions/`; older specs are historical when they conflict.
- Do not delete or move artifacts without following `docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md`.
- Roboflow API keys and `.env` files are gitignored. Never commit credentials.
- Do not upload factory footage, labels, or model artifacts without explicit permission.

## Workflow Orchestration

### 1. Plan for non-trivial work
- For tasks with 3+ steps, architectural decisions, or validation impact, write/update a compact plan before implementation.
- If a proof/validation task has a definition-of-done doc, use that doc as the plan spine.

### 2. Continue by default
- Keep executing the next obvious step until the stated definition of done is met.
- Do not stop after each subtask to summarize progress if the next step is already implied by the PRD, handoff, failure, or verification result.
- Stop only for destructive actions, missing required artifacts, genuinely risky product/technical decisions, or true completion.

### 3. Verification before done
- Never mark work complete without proof: tests, logs, report artifacts, dashboard evidence, or app/runtime verification as appropriate.
- For validation/proof work, use the registry and current docs rather than ad hoc totals.
- Do not claim investor/customer proof from offline replay, timestamp reveal, fake UI updates, or retrospective diagnostics.

### 4. Oracle escalation
- If genuinely stuck after inspecting code/artifacts and trying obvious local debugging, ask Oracle before interrupting Thomas for direction.
- Use `oracle --help` first in a session, prefer dry-run previews, and pass the minimum necessary file set.
- Use browser mode by default unless Thomas explicitly accepts API spend.
- This Mac's working Oracle browser path is the normal Chrome ChatGPT session, not a project `.env` password. Current verified config is in `~/.oracle/config.json`: `browser.manualLogin: false`, `browser.modelStrategy: "ignore"`, `browser.keepBrowser: true`, `browser.hideWindow: false`.
- Chrome cookie DBs to try if Oracle needs an explicit cookie path:
  - `/Users/thomas/Library/Application Support/Google/Chrome/Default/Cookies`
  - `/Users/thomas/Library/Application Support/Google/Chrome/Profile 1/Cookies`
- Reliable Oracle invocation for this repo:
  ```bash
  oracle --engine browser --browser-model-strategy ignore --browser-keep-browser --prompt "<question>" --file "src/**" --file "docs/00_CURRENT_STATE.md"
  ```
- If Oracle says `Unable to locate the ChatGPT model selector button` while ChatGPT is visibly logged in, do **not** ask for a password. Keep `--browser-model-strategy ignore`; the selector UI is the failure, not cookies.

### 5. Lessons and durable knowledge
- Corrections that affect this repo should update the relevant current doc or `tasks/lessons.md`.
- Durable Factory Vision doctrine/research should also be filed in founder-brain/Obsidian.
- Repeatable procedures belong in skills, not in this file.

## Task Management

1. **Plan First**: Write plan to tasks/todo.md with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to tasks/todo.md
6. **Capture Lessons**: Update tasks/lessons.md after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Only touch what's necessary. No side effects with new bugs.

## Judging placement clips (the teacher role — READ BEFORE LABELING)

This station counts finished wire frames placed on the output pallet. The product
is thin wire lattice and is UNBOXABLE from overhead — do not attempt object
detection or bounding boxes. The signal is the ACTION over time (carry -> place ->
leave). Your job as teacher is to judge short clips, and those judgments become the
training labels for a small video model that copies you.

- **Your label IS the training data.** The student model learns only from your
  assert/refute calls. A wrong label teaches the model the wrong thing. Accuracy
  is the whole ballgame — judge every clip like it ships.
- **The question, exactly:** in this clip of the output-pallet zone, did a worker
  PLACE a finished frame onto the pallet/stack? Carry-in, set-down, and the worker
  leaving it there = placement (assert). Walk-by with nothing placed, adjusting the
  pile, a welding flash, or no change = not a placement (refute). A worker merely
  standing at the pallet is NOT a placement unless a frame is deposited.
- **Use the whole sequence, not one still.** The placement is proven by the motion
  across frames, not by any single frame (the new frame is often invisible in the
  pile and occluded mid-place). Reason over before -> during -> after.
- **Ignore welding flashes.** A flash brightens the whole frame uniformly; a real
  placement changes the zone locally. Refute flashes.
- **If you genuinely cannot tell, say low confidence** rather than guessing.
- **Output format:** JSON `{"clip": "<id>", "decision": "assert|refute",
  "confidence": "high|medium|low", "note": "<carry/place/leave evidence or why
  not>"}`. When asked for a 3-vote pass, judge independently; 2-of-3 wins.
- Never label clips from the exam window — those 7 placements are the held-out
  answer key and must never become training data.
