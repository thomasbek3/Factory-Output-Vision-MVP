# Product Spec

This is the short current product spec. The detailed historical spec remains in `docs/PROJECT_SPEC.md`.

## Product

Factory Vision Output Counter is an offline LAN appliance for factory operators. It runs on an Ubuntu edge PC, reads a Reolink camera or demo video source, and counts completed output events in a web dashboard.

## MVP Requirements

- Setup must be possible in under 15 minutes through the web UI.
- The operator draws an output ROI and can optionally configure an operator zone.
- The dashboard shows current runtime count, rate, status, and recent events.
- The app must recover from camera/source drops without manual CLI intervention.
- The system must run without cloud services, Docker, YAML editing, or internet dependency during operation.

## Counting Doctrine

- YOLO object detection is the counting foundation.
- Count lines, blob detection, frame differencing, and generic motion counting are rejected for the MVP.
- Most customer parts require customer-specific detection data and model selection.
- Operator correction controls are allowed as a safety net, not as proof that automated validation worked.

## Validation Doctrine

Real validation means the actual app path counts from ordered processed frames at `1.0x`, with captured events compared to reviewed human truth. See `docs/03_VALIDATION_PIPELINE.md` and `docs/REAL_APP_TEST_CASE_DEFINITION_OF_DONE.md`.
