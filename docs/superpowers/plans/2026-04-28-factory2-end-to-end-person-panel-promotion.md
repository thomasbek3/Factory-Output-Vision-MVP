# Factory2 End-to-End Person/Panel Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Factory2 proof path internally consistent so accepted carried-panel counts are backed by the same person/panel promotion logic in diagnostic receipts and the final proof report.

**Architecture:** Extract the person/panel sidecar interpretation and gate-promotion rule into shared code, then use that shared logic both when building proof reports and when rewriting event-window diagnostic receipts. Finally, have the canonical proof runner refresh diagnostic gate receipts after separation analysis so `factory2.MOV` reaches the success path through one repeatable command instead of proof-only rehydration.

**Tech Stack:** Python 3.9, pytest, existing `scripts/*` proof tooling, existing `app/services/perception_gate.py`

---

### Task 1: Shared Promotion Helper

**Files:**
- Create: `app/services/person_panel_gate_promotion.py`
- Modify: `tests/test_build_morning_proof_report.py`
- Test: `tests/test_build_morning_proof_report.py`

- [ ] **Step 1: Write the failing tests**

Add assertions that the proof-report path still promotes a worker-overlap row only when the sibling `*-person-panel-separation.json` receipt has persistent source-side candidate evidence, and does not promote weak/negative receipts.

- [ ] **Step 2: Run the focused tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_build_morning_proof_report.py -q`

- [ ] **Step 3: Implement the shared helper**

Move the sidecar-path loading, separation-feature extraction, and `evaluate_track(...)` re-run logic out of `scripts/build_morning_proof_report.py` into `app/services/person_panel_gate_promotion.py` so other diagnostic code can reuse the exact same rule.

- [ ] **Step 4: Run the focused tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_build_morning_proof_report.py tests/test_perception_gate.py -q`

- [ ] **Step 5: Commit**

Commit message: `refactor: share person panel gate promotion`


### Task 2: Diagnostic Receipt Refresh

**Files:**
- Modify: `scripts/diagnose_event_window.py`
- Modify: `tests/test_diagnose_event_window.py`
- Test: `tests/test_diagnose_event_window.py`

- [ ] **Step 1: Write the failing tests**

Add a diagnostic-refresh test that starts from a worker-overlap `diagnostic.json` + `track-000005.json`, places a sibling `track-000005-person-panel-separation.json`, runs the diagnostic refresh helper, and expects:
- `perception_gate[track 5].decision == allow_source_token`
- `perception_gate_summary.allowed_source_token_tracks == [5]`
- `track-000005.json` rewritten with promoted gate evidence
- hard-negative manifest updated so the promoted track is removed

- [ ] **Step 2: Run the focused tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_diagnose_event_window.py -q`

- [ ] **Step 3: Implement the refresh path**

Add a helper in `scripts/diagnose_event_window.py` that reads an existing diagnostic directory, rebuilds gate decisions from track evidence plus any sibling person/panel separation receipts, rewrites `track_receipts/*.json`, rewrites `hard_negative_manifest.json`, and updates `diagnostic.json`.

- [ ] **Step 4: Run the focused tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py -q`

- [ ] **Step 5: Commit**

Commit message: `feat: refresh diagnostic gate receipts from person panel evidence`


### Task 3: Canonical Proof Consistency

**Files:**
- Modify: `scripts/run_factory2_morning_proof.py`
- Modify: `tests/test_run_factory2_morning_proof.py`
- Modify: `.hermes/HANDOFF.md`
- Test: `tests/test_run_factory2_morning_proof.py`

- [ ] **Step 1: Write the failing tests**

Add a proof-runner test that creates a worker-overlap diagnostic, has the fake person/panel analyzer emit the sibling separation receipt, and expects the proof command to refresh the diagnostic before the final report so the returned summary shows `accepted_count == 1`.

- [ ] **Step 2: Run the focused tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_run_factory2_morning_proof.py -q`

- [ ] **Step 3: Implement the proof refresh**

After building `factory2_person_panel_separation.json`, call the diagnostic refresh helper for each selected diagnostic before rebuilding the final proof report.

- [ ] **Step 4: Run the required verification**

Run:
- `.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py tests/test_diagnose_event_window.py -q`
- `.venv/bin/python scripts/build_panel_transfer_review_packets.py --force`
- `.venv/bin/python scripts/run_factory2_morning_proof.py --force`

- [ ] **Step 5: Update handoff and commit**

Update `.hermes/HANDOFF.md` with what changed, commands run, proof/test results, blocker, and exact next step.  
Commit message: `feat: unify factory2 diagnostic and proof gate promotion`
