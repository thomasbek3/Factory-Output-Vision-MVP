# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Factory Vision Output Counter — a plug-and-play factory appliance that counts parts in an output zone using a Reolink camera + YOLO object detection on an Ubuntu edge PC. Runs fully offline on LAN. No cloud, no Docker, no YAML. Setup must complete in <15 minutes via a web wizard.

## Vision Pipeline (as of 2026-03-18)

The counting pipeline uses **YOLOv8 object detection** exclusively. Previous approaches (background subtraction, contour/blob detection, frame differencing, count-line crossing) were all red-teamed and rejected as unreliable in real factory environments.

**Two counting modes** (set via `FC_COUNTING_MODE` env var):
- **`track_based`** (default): Frame → ROI mask (output zone polygon) → YOLO inference → filter out person class (class 0) → centroid tracking → count unique objects that appear in and exit the output zone.
- **`event_based`**: Frame → YOLO inference (panel_in_transit.pt) → `EventBasedCounter` groups detection clusters over time → each cluster = +1 count. Designed for non-conveyor factories where a worker carries parts past the camera. Person-ignore masking is auto-disabled. ROI is optional.

**Key architectural decisions**:
- **No count line.** Users draw an output zone (ROI polygon), not a line. Counting = tracking unique YOLO-detected objects within that zone.
- **Person exclusion is always on.** YOLO class 0 (person) is excluded from counting to prevent hands/body parts triggering false counts.
- **Model-agnostic pipeline.** Default model is `yolov8n.pt` (COCO 80-class). For factory parts not in COCO (which is most of them), swap in a custom-trained model via `FC_YOLO_MODEL_PATH`. Zero code changes needed.
- **Custom model training via Roboflow.** Extract frames from customer video → label on Roboflow (auto-label with Grounding DINO + manual review) → fine-tune YOLOv8n (~60-100 labeled images) → deploy. ~1 hour per customer. See `docs/CUSTOM_MODEL_TRAINING.md`.
- **Person-ignore pixel masking should be OFF with custom models.** Custom models trained on "panel in worker's hands" need to see inside the person bounding box. The custom model already excludes person class, making pixel masking unnecessary and harmful.
- **+/- correction buttons on dashboard** are a deliberate safety net, not a crutch. Framed as "AI-assisted counting with operator oversight."

**Why not blob/frame-diff detection?** The worker's body dominates the visual signal (~40% of frame diff vs ~2% for the part). Person masking creates reveal artifacts. Similar parts stacked on each other are nearly invisible to pixel-level detection. Direct object detection via custom YOLO is the only reliable approach for arbitrary factory parts.

**Roboflow integration**: Workspace `thomass-workspace-7u6ay`, projects `wire-mesh-panel` and `panel-in-transit`. API keys in `.env` (gitignored). Downloaded datasets go in `datasets/`. Training runs stored in `training_runs/`. CPU-only training (~20 min for 25 epochs on i7-12700F).

**Trained models** (in `models/` directory):
- `wire_mesh_panel.pt` — Stack detection. 98% precision, 91% recall, mAP50 94.6% (71 training images). NOT useful for counting (detects static stacks).
- `panel_in_transit.pt` / `panel_in_transit.onnx` — Transit detection for event_based counting. 94% precision, 53% recall (47 training images). Needs 150+ images for 80%+ recall target. ONNX export provides no speedup on this CPU (i7-12700F already runs PyTorch at ~60ms/frame).

**Continuous improvement loop** (planned): Use Roboflow API to auto-collect more training images during production, retrain periodically to improve accuracy over time.

## Commands

### Backend (Python / FastAPI)

```bash
# Install dependencies (use the .venv already present)
pip install -r requirements.txt

# Run the backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080

# Run in demo mode (uses demo/demo.mp4 or demo/demo_counter.mp4)
FC_DEMO_MODE=1 FC_DEMO_VIDEO_PATH=demo/demo_counter.mp4 python -m uvicorn app.main:app --host 127.0.0.1 --port 8080

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

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update tasks/lessons.md with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes -- don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests -- then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

### 7. Oracle Escalation Rule
- If you are truly stuck and are about to ask the user what to do next, ask Oracle first.
- "Stuck" means you have already inspected the relevant code/artifacts, tried the obvious local verification/debugging steps, and still do not have a credible next move.
- Do not use Oracle as a substitute for normal code reading. Use it as the escalation path before interrupting the user for direction.
- Oracle on this machine:
  - Binary on PATH: `oracle` (`/opt/homebrew/bin/oracle`)
  - Local checkout: `/Users/thomas/Projects/_research/oracle`
  - Codex skill: `/Users/thomas/.codex/skills/oracle/SKILL.md`
- Before the first Oracle run in a session, run `oracle --help`.
- Prefer a dry-run preview first: `oracle --dry-run summary --files-report -p "<task>" --file "<paths>"`
- When using Oracle here, default to browser mode unless the user explicitly wants an API run or explicitly accepts API spend.
- Always pass both a prompt and the minimum necessary file set. Reattach to existing Oracle sessions instead of spawning duplicates unless a fresh run is clearly needed.

### 8. Definition Of Done Rule
- For Factory2 carried-panel work, "done" does not mean the proof report or diagnostics improved.
- Do not stop at proof-only success.
- The task is only done when the actual counting/runtime path works end to end on `factory2.MOV` and produces the defensible count behavior the proof established.
- If the proof path works but the app/runtime counter path does not, the work is still in progress.
- Do not stop to summarize partial progress while that runtime path is still failing. Keep working until the runtime path counts correctly or you are genuinely blocked.
- If you become genuinely blocked, use the Oracle escalation rule before asking the user what to do next.

### 9. Factory2 Recall Doctrine
- The human truth set for `factory2.MOV` is 23 real carried-panel transfers. That is the current target.
- A single accepted carry is not the finish line. After the first proof/runtime success, the next definition of done is:
  - proof path accepted_count = 23
  - runtime/app path count = 23
  - false positives = 0
- Broad mixed diagnostic windows undercount. Prefer narrow, event-centered windows when building recall-oriented proof sets.
- When merging narrow diagnostics into one proof artifact, freeze or copy the finalized diagnostic directories first. Do not build merged proof results from mutable diagnostics that are still being regenerated.
- Merged proof `accepted_count` must be a distinct-delivery count, not a raw accepted-receipt count. If overlapping windows produce two accepted receipts for the same physical carry, dedupe them at the report layer and keep both receipts only as audit evidence.
- If recall stalls on worker-overlap cases, the next product move is not threshold loosening. Export blocked receipt crops and build a panel-vs-worker separation dataset.
- Runtime-only `approved_delivery_chain` events are not automatically proof-eligible. If runtime lineage shows `synthetic_approved_chain_token`, do not promote that event into proof receipts or use it to raise `accepted_count`.
- Current honest state after runtime-lineage audit: runtime/app path reaches `23`, but proof stays at `21` because the remaining `305.708s` and `425.012s` events are synthetic approved-chain tokens rather than fresh source-backed proof receipts.
- The corrected source-history-driven rescue searches for `305.708s` and `425.012s` are now exhausted work. Across the focused `5/8/10fps` lineage windows, both events still collapse into `shared_source_lineage_no_distinct_proof_receipt`.
- Synthetic `approved_delivery_chain` events are operational/runtime counts, not source-token-backed proof authority. Do not mint fake `source_token_id` or `source_bbox` values for them; serialize them as `count_authority = runtime_inferred_only`.
- The current count-authority ledger is `data/reports/factory2_count_authority_ledger.v1.json`: runtime total `23`, proof total `21`, inherited live source token `11`, synthetic with overlapping proof `10`, synthetic without distinct proof `2`.
- Roboflow is acceptable for offline private annotation/training of those hard crops, but it is not a live runtime dependency and should not be treated as the immediate fix by itself.
- Demo-mode app verification has a trap: `app/services/frame_reader.py` uses `ffmpeg -stream_loop -1` for demo files. Do not treat a long-running demo `counts_this_hour` total as a one-pass truth count for `factory2.MOV` unless you control the loop boundary or use a no-loop harness.
- Active PRDs for this phase:
  - `docs/PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md`
  - `docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md`

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
