# Factory Vision Output Counter (MVP)
### Plug-and-Play Factory Output Monitoring using Reolink RLC-510WA + Ubuntu Edge PC

---

## What this is
This is **not** "a computer vision project."

This is a **factory appliance** that must:
- Start on boot
- Heal itself when the camera stream drops
- Explain problems in plain language
- Be configurable by a shop owner in **under 15 minutes**
- Require **no CLI after install**
- Run fully offline on a LAN

If setup takes >15 minutes, it fails.

---

## What it does (MVP)
- User enters camera IP + login in a local web UI
- User draws:
  - Output ROI (polygon)
  - Optional operator zone (polygon)
- User clicks "Calibrate" to set baseline output rate
- User clicks "Start Monitoring"

System automatically:
- Counts parts/events in the output zone (per minute/hour)
- Detects **Stop** (zero count for N minutes)
- Detects **Drop** (rolling rate < 60% baseline for M minutes)
- Optionally detects **Operator Absence** ONLY during drop
- Displays a simple **Green / Yellow / Red** status
- Logs events
- Auto-reconnects RTSP if the stream drops
- Exposes diagnostics and a support bundle endpoint

---

## What it does NOT do (MVP)
- No MES/ERP platform
- No PLC integration required
- No cloud required
- No Docker
- No YAML editing
- No ML training required

---

## Hardware assumptions
- Camera: Reolink RLC-510WA
- Edge compute: Ubuntu mini PC (CPU-only OK)
- Network: Ethernet LAN
- Browser: any device on LAN

---

## Repo documentation (current source of truth)

Start here:

- `docs/00_CURRENT_STATE.md` (verified cases, claim boundary, non-negotiables)
- `docs/01_PRODUCT_SPEC.md` (current MVP product definition)
- `docs/02_ARCHITECTURE.md` (short current architecture map)
- `docs/03_VALIDATION_PIPELINE.md` (new-video validation workflow)
- `docs/04_TEST_CASE_REGISTRY.md` (registry and manifest rules)
- `docs/05_OPERATOR_RUNBOOK.md` (dashboard operator workflow)
- `docs/06_DEVELOPER_RUNBOOK.md` (developer commands and guardrails)
- `docs/KNOWN_LIMITATIONS.md` (honest product limits)

Detailed references remain available in `docs/PROJECT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`, `docs/UX_SPEC.md`, `docs/TEST_PLAN.md`, and the specific Factory2/IMG workflow docs. Historical docs live under `docs/ARCHIVED_DONOTREAD/` and `docs/archived/`.

Validation is now registry-backed:

- `validation/registry.json`
- `validation/test_cases/factory2.json`
- `validation/test_cases/img3262.json`
- `validation/test_cases/img3254_clean22.json`

---

## Verified Factory2 real-time demo

Alias: `Test Case 1`.

Run the backend only:

```bash
.venv/bin/python scripts/start_factory2_demo_app.py --port 8091
```

Run backend + frontend dev stack:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Open `http://127.0.0.1:5173/dashboard`, click `Start monitoring`, and verify Runtime Total climbs to `23`.

Primary proof artifact:

```text
data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json
```

Expected result:

```text
matched_count: 23
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
```

---

## Success criteria (must pass)
- Setup wizard can complete in <15 minutes
- RTSP drop triggers reconnect automatically (no user action)
- Counting works in demo mode using a video file
- Stop/Drop logic triggers correctly
- Troubleshooting page explains failures clearly and offers actions
- Support bundle exports logs + db + snapshot

---

## Non-functional constraints
- CPU-only, cap processing at 10 FPS
- Reader ingest defaults to 12 FPS for smoother demo and operator validation
- Dashboard/troubleshooting snapshot polling refreshes at 1-second intervals
- No memory leaks in 8-hour run
- No thread deadlocks on reconnect
- Clear user-facing errors (no stack traces in UI)

---
