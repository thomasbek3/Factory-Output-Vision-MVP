# Factory2 Proof Alignment To 23 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the auditable Factory2 proof path to the now-verified `23`-count runtime result by converting the `8` runtime-only events into proof-grade diagnostic windows and refreshed receipts.

**Architecture:** Treat the no-loop runtime audit as the event-discovery source, not as proof by itself. Build a deterministic proof-alignment queue from the runtime-only reconstruction rows, materialize missing diagnostic windows around those events, and then rerun the frozen proof/report path until accepted proof receipts match the runtime event list.

**Tech Stack:** Python 3.9, pytest, existing Factory2 diagnostic/report scripts, JSON artifacts under `data/reports/` and `data/diagnostics/`.

---

### Task 1: Build The Proof-Alignment Queue

**Files:**
- Create: `scripts/build_factory2_proof_alignment_queue.py`
- Create: `tests/test_build_factory2_proof_alignment_queue.py`
- Input reports:
  - `data/reports/factory2_truth_reconstruction.gap45_recentdedupe.v0.json`
  - `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json`
- Output:
  - `data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json`

- [ ] **Step 1: Write the failing test**

```python
def test_build_proof_alignment_queue_emits_runtime_only_targets(tmp_path) -> None:
    reconstruction_path = tmp_path / "reconstruction.json"
    output_path = tmp_path / "queue.json"
    reconstruction_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_id": "factory2-runtime-only-0001",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 42.701, "track_id": 11, "count_total": 3},
                    },
                    {
                        "event_id": "factory2-runtime-only-0002",
                        "status": "runtime_only_needs_receipt_match",
                        "runtime_event": {"event_ts": 60.502, "track_id": 16, "count_total": 4},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_proof_alignment_queue(
        reconstruction_path=reconstruction_path,
        output_path=output_path,
        force=True,
    )

    assert report["runtime_only_count"] == 2
    assert report["queue_count"] == 2
    assert report["queue"][0]["event_id"] == "factory2-runtime-only-0001"
    assert report["queue"][0]["suggested_start_seconds"] == 22.701
    assert report["queue"][0]["suggested_end_seconds"] == 62.701
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_factory2_proof_alignment_queue.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing `build_proof_alignment_queue`.

- [ ] **Step 3: Write minimal implementation**

```python
def build_proof_alignment_queue(*, reconstruction_path: Path, output_path: Path, force: bool) -> dict[str, Any]:
    payload = json.loads(reconstruction_path.read_text(encoding="utf-8"))
    runtime_only = [
        row for row in (payload.get("events") or [])
        if row.get("status") == "runtime_only_needs_receipt_match"
    ]
    queue = []
    for row in runtime_only:
        event_ts = float(row["runtime_event"]["event_ts"])
        queue.append(
            {
                "event_id": row["event_id"],
                "runtime_track_id": int(row["runtime_event"]["track_id"]),
                "event_ts": round(event_ts, 3),
                "suggested_start_seconds": round(max(0.0, event_ts - 20.0), 3),
                "suggested_end_seconds": round(event_ts + 20.0, 3),
            }
        )
    result = {
        "schema_version": "factory2-proof-alignment-queue-v1",
        "runtime_only_count": len(runtime_only),
        "queue_count": len(queue),
        "queue": queue,
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_factory2_proof_alignment_queue.py -q`
Expected: PASS

- [ ] **Step 5: Generate the real queue**

Run:

```bash
.venv/bin/python -m scripts.build_factory2_proof_alignment_queue \
  --reconstruction /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_truth_reconstruction.gap45_recentdedupe.v0.json \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json \
  --force
```

Expected: `queue_count == 8`

- [ ] **Step 6: Commit**

```bash
git add scripts/build_factory2_proof_alignment_queue.py tests/test_build_factory2_proof_alignment_queue.py \
  data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json
git commit -m "feat: add factory2 proof alignment queue"
```

### Task 2: Materialize Missing Runtime-Backed Diagnostics

**Files:**
- Create: `scripts/build_factory2_runtime_backed_diagnostics.py`
- Create: `tests/test_build_factory2_runtime_backed_diagnostics.py`
- Reuse:
  - `scripts/diagnose_event_window.py`
  - `data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json`
- Output root:
  - `data/diagnostics/event-windows/factory2-runtime-proof-*`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_backed_diagnostics_builds_command_rows(tmp_path) -> None:
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "event_id": "factory2-runtime-only-0001",
                        "event_ts": 42.701,
                        "suggested_start_seconds": 22.701,
                        "suggested_end_seconds": 62.701,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_runtime_backed_diagnostics_plan(queue_path=queue_path)

    assert report["diagnostic_count"] == 1
    assert report["diagnostics"][0]["diagnostic_slug"] == "factory2-runtime-proof-0001-023-063s-panel-v1-5fps"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_factory2_runtime_backed_diagnostics.py -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def diagnostic_slug(event_id: str, start_seconds: float, end_seconds: float) -> str:
    return f"{event_id.replace('factory2-runtime-only', 'factory2-runtime-proof')}-{int(start_seconds):03d}-{int(end_seconds):03d}s-panel-v1-5fps"
```

```python
def build_runtime_backed_diagnostics_plan(*, queue_path: Path) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8")).get("queue") or []
    rows = []
    for row in queue:
        rows.append(
            {
                "event_id": row["event_id"],
                "diagnostic_slug": diagnostic_slug(
                    row["event_id"],
                    float(row["suggested_start_seconds"]),
                    float(row["suggested_end_seconds"]),
                ),
            }
        )
    return {"diagnostic_count": len(rows), "diagnostics": rows}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_factory2_runtime_backed_diagnostics.py -q`
Expected: PASS

- [ ] **Step 5: Build the first real diagnostic slice**

Run:

```bash
.venv/bin/python -m scripts.diagnose_event_window \
  --video /Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV \
  --calibration /Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json \
  --model /Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt \
  --person-model /Users/thomas/Projects/Factory-Output-Vision-MVP/yolo11n.pt \
  --out-dir /Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-runtime-proof-0001-023-063s-panel-v1-5fps \
  --start 22.701 --end 62.701 --fps 5 --force
```

Expected: new diagnostic JSON and track receipts on disk for the first runtime-only event band.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_factory2_runtime_backed_diagnostics.py tests/test_build_factory2_runtime_backed_diagnostics.py \
  data/diagnostics/event-windows/factory2-runtime-proof-0001-023-063s-panel-v1-5fps
git commit -m "feat: add runtime-backed proof diagnostics"
```

---

## Execution Notes (2026-04-28)

- The original runtime-only reconstruction queue (`8` events) was too coarse by itself; a naive union of those windows regressed proof quality.
- A direct proof-set optimizer over the current narrow proof winners plus nearby gap-region windows found a much stronger existing set:
  - `accepted_count: 19`
  - `covered_runtime_events: 19`
  - artifact:
    - `data/reports/factory2_optimized_proof_set.runtime23_live_narrow_v1.json`
- New focused diagnostics recovered two more proof events:
  - `factory2-review-0019-000-010s-panel-v1-8fps` recovered `5.5s`
  - `factory2-review-0016-274-294s-panel-v1-5fps` recovered `286.408s`
- Current best proof artifact:
  - `data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json`
  - `accepted_count: 21`
  - remaining uncovered runtime timestamps:
    - `305.708`
    - `425.012`
- The remaining two misses currently collapse into:
  - an earlier accepted proof carry
  - plus a later `output_only_no_source_token` stub
- That means the next move is no longer “more generic perception windows.” It is either:
  - a non-cheating receipt-building strategy for split proof chains, or
  - an explicit documented proof/runtime divergence for those last two events.

### Task 3: Refresh The Proof Set To Match Runtime

**Files:**
- Modify: `scripts/build_morning_proof_report.py`
- Modify: `scripts/run_factory2_morning_proof.py`
- Modify: `.hermes/HANDOFF.md`
- Test:
  - `tests/test_run_factory2_morning_proof.py`
  - `tests/test_build_morning_proof_report.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_backed_diagnostics_can_be_appended_to_proof_defaults() -> None:
    paths = existing_paths(DEFAULT_DIAGNOSTICS + ["data/diagnostics/event-windows/factory2-runtime-proof-0001-023-063s-panel-v1-5fps/diagnostic.json"])
    assert any("factory2-runtime-proof-0001-023-063s-panel-v1-5fps" in str(path) for path in paths)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py -q`
Expected: FAIL until runtime-backed diagnostics are wired into the rerun path.

- [ ] **Step 3: Write minimal implementation**

```python
RUNTIME_BACKED_DIAGNOSTICS = [
    "data/diagnostics/event-windows/factory2-runtime-proof-0001-023-063s-panel-v1-5fps/diagnostic.json",
]

DEFAULT_DIAGNOSTICS = LEGACY_DIAGNOSTICS + RUNTIME_BACKED_DIAGNOSTICS
```

- [ ] **Step 4: Run proof and verify counts move toward runtime**

Run:

```bash
.venv/bin/python -m scripts.run_factory2_morning_proof --force \
  --report-json /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.runtime_backed.json \
  --report-md /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.runtime_backed.md \
  --run-summary-json /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_run_summary.runtime_backed.json
```

Expected: accepted proof count increases from `15`, and the proof report exposes fewer runtime-only rows when reconstruction is rerun.

- [ ] **Step 5: Rebuild reconstruction and verify convergence**

Run:

```bash
.venv/bin/python -m scripts.reconstruct_factory2_truth_candidates \
  --proof-report /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.runtime_backed.json \
  --runtime-audit /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json \
  --manual-labels /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_track_labels.manual_v1.json \
  --diagnostics-root /Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_truth_reconstruction.runtime_backed.json \
  --force
```

Expected: `runtime_only_count` trends to `0`.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_morning_proof_report.py scripts/run_factory2_morning_proof.py .hermes/HANDOFF.md \
  data/reports/factory2_morning_proof_report.runtime_backed.json \
  data/reports/factory2_truth_reconstruction.runtime_backed.json
git commit -m "feat: align factory2 proof with runtime audit"
```
