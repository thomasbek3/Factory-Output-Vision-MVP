# Architecture

This is the short current architecture map. The detailed component spec remains in `docs/ARCHITECTURE.md`.

## Runtime Path

```text
Camera or demo video
  -> FrameReader
  -> VisionWorker
  -> YOLO detector
  -> counting mode
  -> runtime state and event history
  -> FastAPI REST/WebSocket/MJPEG
  -> React dashboard
```

## Counting Modes

- `track_based`: ROI-driven object tracking for output-zone counting.
- `event_based`: detection-cluster event counting for carried/placed-piece workflows.

The verified Factory2, IMG_3262, and IMG_3254 app proofs use `event_based`.

## Backend

- `app/main.py`: FastAPI app creation and lifespan.
- `app/workers/vision_worker.py`: frame processing, detection, counting, state updates.
- `app/services/frame_reader.py`: source-clock file and stream frame reading.
- `app/services/runtime_event_counter.py`: event-based count grouping and event emission.
- `app/core/settings.py`: `FC_*` environment configuration.

## Frontend

- `frontend/src/features/dashboard/`: visible Runtime Total, source preview, status, and event view.
- `frontend/src/features/wizard/`: setup and calibration flow.
- `frontend/src/features/troubleshooting/`: diagnostics and debug views.

## Validation Surface

The validation product surface is now:

- `validation/registry.json`
- `validation/test_cases/*.json`
- `validation/schemas/*.schema.json`
- `scripts/validate_video.py`
- `scripts/register_test_case.py`

Historical research scripts remain in `scripts/` until they can be moved without breaking imports/tests. They are not the primary product path.
