# Factory Vision — Agent Guide

This file provides repo-local guidance for AI coding assistants working in this repository. Keep it short: route durable doctrine to `docs/` and founder-brain/Obsidian rather than duplicating it here.

## Current Source Of Truth

Start with the concise current docs before relying on older task logs or research notes:

- `docs/00_CURRENT_STATE.md`
- `docs/01_PRODUCT_SPEC.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_VALIDATION_PIPELINE.md`
- `docs/04_TEST_CASE_REGISTRY.md`
- `docs/06_DEVELOPER_RUNBOOK.md`
- `docs/07_ARTIFACT_STORAGE.md`
- `docs/KNOWN_LIMITATIONS.md`
- `validation/registry.json`

## What This Is

Factory Vision Output Counter — a plug-and-play factory appliance that counts parts in an output zone using a Reolink camera + YOLO object detection on an Ubuntu edge PC. Runs fully offline on LAN. No cloud, no Docker, no YAML. Setup must complete in <15 minutes via a web wizard.

## Current Context Routing

This file is a routing layer, not the project brain. Before changing behavior or making proof claims:

1. Read `docs/00_CURRENT_STATE.md` for current validated cases, claim boundaries, and non-negotiables.
2. Read the relevant canonical doc from the list above.
3. For durable product doctrine/research history, consult founder-brain / Obsidian Factory Vision pages.
4. For implementation truth, inspect the live code, validation registry, reports, tests, and logs.

Do not rely on older task logs, archived docs, chat memory, or stale AGENTS prose when a current doc or artifact exists.

## Critical Claim Boundary

Current app evidence proves file-backed live counting at real-time speed for promoted/verified cases listed in `docs/00_CURRENT_STATE.md`. It does **not** prove live Reolink/RTSP field operation until the same runtime path is validated on an actual live camera stream.

Factory Vision project doctrine belongs in Obsidian/project docs, not Hermes always-loaded memory. This `AGENTS.md` should point agents to the right sources and commands only.

## Commands

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
- `app/services/person_detector.py` — Optional YOLOv8 person detection (operator zone / person-ignore pixel masking). NOTE: should be disabled when using custom-trained models (custom models already exclude persons; pixel masking blacks out parts held by workers)
- `app/services/camera_probe.py` — ffprobe-based RTSP stream validation
- `app/services/video_source.py` — RTSP URL builder for Reolink cameras
- `app/db/` — SQLite repos: `database.py` (init), `config_repo.py`, `count_repo.py`, `event_repo.py`, `health_repo.py`
- `app/core/settings.py` — All config via `FC_*` environment variables (no .env file parsing, just `os.getenv`)
- `app/core/logging.py` — Structured logging setup

**Frontend** (`frontend/src/`): React 19 + React Router + TypeScript + Vite

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
- CPU-only inference (no CUDA GPU), capped at 10 FPS processing. Training also CPU-only for now.
- **No blob detection, no count lines, no frame differencing.** YOLO object detection is the only counting method. These alternatives were red-teamed and rejected (see `tasks/lessons.md`).
- Custom YOLO model training per customer is a core part of the product, not an afterthought. Most factory parts are not in COCO.
- FastAPI serves the React build from `frontend/dist` — if missing, returns 503.
- The `build/windows-installer/` directory contains a snapshot of the app payload for the Windows installer EXE at `dist/windows-installer/`. It is a copy, not the source of truth.
- `docs/ARCHIVED_DONOTREAD/` contains superseded specs — ignore them.
- Authoritative specs live in `docs/PROJECT_SPEC.md`, `docs/UX_SPEC.md`, and the other non-archived docs.
- Roboflow API keys and `.env` files are gitignored. Never commit credentials.

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
