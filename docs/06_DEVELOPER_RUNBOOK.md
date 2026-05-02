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

1. Copy the source video into `demo/` or another repo-local video path.
2. Create or update a manifest under `validation/test_cases/`.
3. Run `scripts/validate_video.py --case-id <case-id> --dry-run`.
4. Generate or review the human truth CSV and ledger.
5. Run the visible dashboard path at `1.0x`.
6. Capture app events and compare to truth.
7. Register the manifest with `scripts/register_test_case.py`.

## Guardrails

- Do not delete historical artifacts during cleanup.
- Do not present timestamp replay, deterministic reveal, or offline retrospective counting as app proof.
- Do not claim RTSP/Reolink field validation until it has a real live-camera manifest and clean comparison.
- Do not move research scripts without updating tests/imports in the same change.
