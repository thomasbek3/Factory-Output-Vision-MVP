# Factory2 Overnight Final-Two To Goal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push Factory2 from the current honest state to the next real decision point by proving fresh source lineage for the remaining proof gaps at `305.708s` and `425.012s`, or by explicitly locking in a truthful `runtime 23 / proof 21` divergence if no fresh lineage exists.

**Architecture:** Keep the committed runtime result (`23`) as the event-discovery source and the committed `21`-count proof artifact as the audit baseline. Build a targeted search loop around the two unresolved runtime events: generate candidate event-centered diagnostic windows, run them reproducibly, score whether they produce a distinct proof source lineage rather than restating an already-accepted carry, and then either promote true fresh receipts into proof or codify an explicit divergence artifact instead of cheating with thresholds.

**Tech Stack:** Python 3.9, pytest, existing Factory2 diagnostic/report scripts, JSON artifacts under `data/reports/` and `data/diagnostics/`, repo `.venv` for video/vision dependencies.

---

## File Map

**Plan-owned files**

- Create: `scripts/build_factory2_final_gap_search_plan.py`
- Create: `scripts/run_factory2_final_gap_search.py`
- Create: `scripts/build_factory2_final_gap_search_report.py`
- Create: `tests/test_build_factory2_final_gap_search_plan.py`
- Create: `tests/test_run_factory2_final_gap_search.py`
- Create: `tests/test_build_factory2_final_gap_search_report.py`
- Modify: `scripts/build_factory2_runtime_event_receipt_packets.py`
- Modify: `scripts/build_morning_proof_report.py` only if the scorer needs one more audit field
- Modify: `.hermes/HANDOFF.md`
- Modify: `tasks/lessons.md`

**Primary input artifacts**

- `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json`
- `data/reports/factory2_truth_reconstruction.gap45_recentdedupe.v0.json`
- `data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json`
- `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json`

**Primary output artifacts**

- `data/reports/factory2_final_gap_search_plan.v1.json`
- `data/diagnostics/event-windows/factory2-final-gap-search-*`
- `data/reports/factory2_final_gap_search_report.v1.json`
- optionally:
  - `data/reports/factory2_morning_proof_report.optimized_plus_final_gap_v1.json`
  - or an explicit divergence artifact if proof still stops at `21`

---

### Task 1: Build The Final-Gap Search Plan

**Files:**
- Create: `scripts/build_factory2_final_gap_search_plan.py`
- Create: `tests/test_build_factory2_final_gap_search_plan.py`
- Reuse:
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
  - `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json`
- Output:
  - `data/reports/factory2_final_gap_search_plan.v1.json`

- [ ] **Step 1: Write the failing test**

```python
def test_build_final_gap_search_plan_generates_window_grid_for_unresolved_events(tmp_path) -> None:
    packets_path = tmp_path / "packets.json"
    output_path = tmp_path / "plan.json"
    packets_path.write_text(
        json.dumps(
            {
                "packets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "recommendation": "shared_source_lineage_no_distinct_proof_receipt",
                        "covering_diagnostic_paths": [
                            "data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json"
                        ],
                        "prior_accepted_receipt": {
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                            "source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_final_gap_search_plan(
        packets_path=packets_path,
        output_path=output_path,
        lead_seconds=[4.0, 6.0],
        tail_seconds=[2.0],
        fps_values=[5.0, 8.0],
        force=True,
    )

    assert payload["event_count"] == 1
    assert payload["candidate_count"] == 4
    assert payload["targets"][0]["event_id"] == "factory2-runtime-only-0007"
    assert payload["targets"][0]["candidates"][0]["start_seconds"] == 299.708
    assert payload["targets"][0]["candidates"][0]["end_seconds"] == 307.708
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_factory2_final_gap_search_plan.py -q`
Expected: FAIL with missing module or missing `build_final_gap_search_plan`.

- [ ] **Step 3: Write minimal implementation**

```python
def build_final_gap_search_plan(
    *,
    packets_path: Path,
    output_path: Path,
    lead_seconds: list[float],
    tail_seconds: list[float],
    fps_values: list[float],
    force: bool,
) -> dict[str, Any]:
    packets = json.loads(packets_path.read_text(encoding="utf-8")).get("packets") or []
    targets = []
    for packet in packets:
        if packet.get("recommendation") != "shared_source_lineage_no_distinct_proof_receipt":
            continue
        event_ts = float(packet["event_ts"])
        candidates = []
        for lead in lead_seconds:
            for tail in tail_seconds:
                for fps in fps_values:
                    candidates.append(
                        {
                            "event_id": packet["event_id"],
                            "event_ts": round(event_ts, 3),
                            "start_seconds": round(max(0.0, event_ts - lead), 3),
                            "end_seconds": round(event_ts + tail, 3),
                            "fps": fps,
                        }
                    )
        targets.append({"event_id": packet["event_id"], "event_ts": round(event_ts, 3), "candidates": candidates})
    payload = {
        "schema_version": "factory2-final-gap-search-plan-v1",
        "event_count": len(targets),
        "candidate_count": sum(len(item["candidates"]) for item in targets),
        "targets": targets,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_factory2_final_gap_search_plan.py -q`
Expected: PASS

- [ ] **Step 5: Generate the real search plan**

Run:

```bash
.venv/bin/python scripts/build_factory2_final_gap_search_plan.py \
  --packets /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_final_gap_search_plan.v1.json \
  --lead-seconds 4 --lead-seconds 6 --lead-seconds 8 --lead-seconds 10 --lead-seconds 12 \
  --tail-seconds 2 --tail-seconds 3 --tail-seconds 4 --tail-seconds 6 \
  --fps 5 --fps 8 --fps 10 \
  --force
```

Expected: candidates for exactly the two unresolved events, concentrated around `305.708s` and `425.012s`.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_factory2_final_gap_search_plan.py tests/test_build_factory2_final_gap_search_plan.py \
  data/reports/factory2_final_gap_search_plan.v1.json
git commit -m "feat: add factory2 final-gap search plan"
```

### Task 2: Run The Diagnostic Search Sweep

**Files:**
- Create: `scripts/run_factory2_final_gap_search.py`
- Create: `tests/test_run_factory2_final_gap_search.py`
- Reuse:
  - `scripts/diagnose_event_window.py`
  - `scripts/build_morning_proof_report.py`
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
- Output root:
  - `data/diagnostics/event-windows/factory2-final-gap-search-*`

- [ ] **Step 1: Write the failing test**

```python
def test_run_final_gap_search_writes_candidate_manifest_without_running_vision(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "search.json"
    plan_path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "event_ts": 305.708,
                        "candidates": [
                            {
                                "event_id": "factory2-runtime-only-0007",
                                "event_ts": 305.708,
                                "start_seconds": 299.708,
                                "end_seconds": 307.708,
                                "fps": 8.0,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_final_gap_search(
        plan_path=plan_path,
        output_path=output_path,
        diagnostic_runner=lambda **kwargs: {"diagnostic_path": kwargs["out_dir"] / "diagnostic.json"},
        force=True,
    )

    assert payload["result_count"] == 1
    assert payload["results"][0]["event_id"] == "factory2-runtime-only-0007"
    assert payload["results"][0]["diagnostic_slug"].startswith("factory2-final-gap-search-0007")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_factory2_final_gap_search.py -q`
Expected: FAIL with missing module or missing `run_final_gap_search`.

- [ ] **Step 3: Write minimal implementation**

```python
def run_final_gap_search(
    *,
    plan_path: Path,
    output_path: Path,
    diagnostic_runner: Callable[..., dict[str, Any]],
    force: bool,
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    results = []
    for target in plan.get("targets") or []:
        for index, candidate in enumerate(target.get("candidates") or [], start=1):
            slug = (
                f"factory2-final-gap-search-{str(target['event_id']).split('-')[-1]}-"
                f"{int(candidate['start_seconds']):03d}-{int(candidate['end_seconds']):03d}s-"
                f"{int(candidate['fps'])}fps-v{index:02d}"
            )
            out_dir = Path("data/diagnostics/event-windows") / slug
            diagnostic_runner(out_dir=out_dir, start_timestamp=candidate["start_seconds"], end_timestamp=candidate["end_seconds"], fps=candidate["fps"])
            results.append(
                {
                    "event_id": target["event_id"],
                    "diagnostic_slug": slug,
                    "start_seconds": candidate["start_seconds"],
                    "end_seconds": candidate["end_seconds"],
                    "fps": candidate["fps"],
                    "diagnostic_path": str(out_dir / "diagnostic.json"),
                }
            )
    payload = {"schema_version": "factory2-final-gap-search-run-v1", "result_count": len(results), "results": results}
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_factory2_final_gap_search.py -q`
Expected: PASS

- [ ] **Step 5: Run the real search sweep**

Run:

```bash
.venv/bin/python scripts/run_factory2_final_gap_search.py \
  --plan /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_final_gap_search_plan.v1.json \
  --video /Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV \
  --calibration /Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json \
  --model /Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt \
  --person-model /Users/thomas/Projects/Factory-Output-Vision-MVP/yolo11n.pt \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_final_gap_search_run.v1.json \
  --force
```

Expected: a bounded set of search diagnostics under `data/diagnostics/event-windows/factory2-final-gap-search-*`.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_factory2_final_gap_search.py tests/test_run_factory2_final_gap_search.py \
  data/reports/factory2_final_gap_search_run.v1.json data/diagnostics/event-windows/factory2-final-gap-search-*
git commit -m "feat: run factory2 final-gap diagnostic search"
```

### Task 3: Score Search Results Against Fresh Source Lineage

**Files:**
- Create: `scripts/build_factory2_final_gap_search_report.py`
- Create: `tests/test_build_factory2_final_gap_search_report.py`
- Reuse:
  - `scripts/build_morning_proof_report.py`
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
  - `data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json`
- Output:
  - `data/reports/factory2_final_gap_search_report.v1.json`

- [ ] **Step 1: Write the failing test**

```python
def test_build_final_gap_search_report_marks_restated_lineage_as_nonrecovering(tmp_path) -> None:
    run_path = tmp_path / "run.json"
    proof_path = tmp_path / "proof.json"
    output_path = tmp_path / "report.json"
    run_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "diagnostic_slug": "factory2-final-gap-search-0007-299-307s-8fps-v01",
                        "diagnostic_path": "diag/diagnostic.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    proof_path.write_text(
        json.dumps(
            {
                "decision_receipt_index": {
                    "accepted": [
                        {
                            "diagnostic_path": "diag/diagnostic.json",
                            "track_id": 2,
                            "source_token_key": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002",
                            "counts_toward_accepted_total": True,
                            "receipt_timestamps": {"first": 303.1, "last": 303.7},
                        }
                    ],
                    "suppressed": [
                        {
                            "diagnostic_path": "diag/diagnostic.json",
                            "track_id": 3,
                            "reason": "static_stack_edge",
                            "receipt_timestamps": {"first": 306.9, "last": 306.9},
                        }
                    ],
                    "uncertain": [],
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_final_gap_search_report(
        search_run_path=run_path,
        proof_baseline_path=proof_path,
        output_path=output_path,
        baseline_source_keys={"factory2-runtime-only-0007": "factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002"},
        force=True,
    )

    assert payload["event_summaries"][0]["recommendation"] == "restated_prior_source_lineage"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_factory2_final_gap_search_report.py -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def build_final_gap_search_report(
    *,
    search_run_path: Path,
    proof_baseline_path: Path,
    output_path: Path,
    baseline_source_keys: dict[str, str],
    force: bool,
) -> dict[str, Any]:
    search = json.loads(search_run_path.read_text(encoding="utf-8"))
    proof = json.loads(proof_baseline_path.read_text(encoding="utf-8"))
    accepted = proof.get("decision_receipt_index", {}).get("accepted") or []
    accepted_by_diag = {row["diagnostic_path"]: row for row in accepted if row.get("counts_toward_accepted_total")}
    summaries = []
    for row in search.get("results") or []:
        accepted_row = accepted_by_diag.get(row["diagnostic_path"])
        baseline_key = baseline_source_keys.get(row["event_id"])
        if accepted_row and accepted_row.get("source_token_key") and accepted_row["source_token_key"] != baseline_key:
            recommendation = "fresh_source_lineage_candidate"
        elif accepted_row:
            recommendation = "restated_prior_source_lineage"
        else:
            recommendation = "no_accepted_receipt"
        summaries.append({"event_id": row["event_id"], "diagnostic_slug": row["diagnostic_slug"], "recommendation": recommendation})
    payload = {"schema_version": "factory2-final-gap-search-report-v1", "event_summaries": summaries}
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_factory2_final_gap_search_report.py -q`
Expected: PASS

- [ ] **Step 5: Score the real search**

Run:

```bash
.venv/bin/python scripts/build_factory2_final_gap_search_report.py \
  --search-run /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_final_gap_search_run.v1.json \
  --proof-baseline /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json \
  --packets /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_final_gap_search_report.v1.json \
  --force
```

Expected:
- either at least one candidate becomes `fresh_source_lineage_candidate`
- or all candidates reduce to `restated_prior_source_lineage | no_accepted_receipt | output_only_stub_only`

- [ ] **Step 6: Commit**

```bash
git add scripts/build_factory2_final_gap_search_report.py tests/test_build_factory2_final_gap_search_report.py \
  data/reports/factory2_final_gap_search_report.v1.json
git commit -m "feat: score factory2 final-gap diagnostic search"
```

### Task 4: Decision Gate For The Goal

**Files:**
- Modify: `.hermes/HANDOFF.md`
- Modify: `tasks/lessons.md`
- Optionally modify:
  - `scripts/build_factory2_runtime_backed_proof_set.py`
  - `scripts/optimize_factory2_proof_set.py`
  - `scripts/run_factory2_morning_proof.py`

- [ ] **Step 1: If fresh lineage exists, write the failing proof update test**

```python
def test_runtime_backed_proof_set_adds_fresh_final_gap_diagnostic(tmp_path) -> None:
    queue_path = tmp_path / "queue.json"
    output_path = tmp_path / "proof_set.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "event_id": "factory2-runtime-only-0007",
                        "preferred_diagnostic_path": "data/diagnostics/event-windows/factory2-final-gap-search-0007-299-307s-8fps-v01/diagnostic.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_runtime_backed_proof_set(
        queue_path=queue_path,
        output_path=output_path,
        default_diagnostic_paths=[],
        force=True,
    )

    assert payload["diagnostic_paths"] == [
        "data/diagnostics/event-windows/factory2-final-gap-search-0007-299-307s-8fps-v01/diagnostic.json"
    ]
```

- [ ] **Step 2: If fresh lineage exists, promote and rerun proof**

Run:

```bash
.venv/bin/python scripts/build_factory2_runtime_backed_proof_set.py \
  --queue /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_proof_alignment_queue.gap45_recentdedupe.json \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_backed_proof_set.final_gap_v1.json \
  --force
```

Then rerun:

```bash
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Expected: proof rises above `21` only if a diagnostic truly contributes fresh lineage.

- [ ] **Step 3: If fresh lineage does not exist, write the divergence artifact**

```json
{
  "schema_version": "factory2-proof-runtime-divergence-v1",
  "runtime_count": 23,
  "proof_honest_ceiling": 21,
  "divergent_events": [
    {
      "event_ts": 305.708,
      "status": "shared_source_lineage_no_distinct_proof_receipt"
    },
    {
      "event_ts": 425.012,
      "status": "shared_source_lineage_no_distinct_proof_receipt"
    }
  ]
}
```

- [ ] **Step 4: Update doctrine and next-step guidance**

Record:
- what search windows were tried
- whether any fresh source lineage appeared
- whether the true next move is:
  - proof receipt construction work, or
  - new training/data/model work on those exact split-delivery regimes

- [ ] **Step 5: Commit**

```bash
git add .hermes/HANDOFF.md tasks/lessons.md data/reports/factory2_final_gap_search_report.v1.json
git commit -m "docs: record factory2 final-gap proof outcome"
```

---

## Review Notes Before Execution

1. The committed runtime truth is already `23`, so tonight’s work is **not** “fix counting core.” It is proof recovery or honest divergence.
2. The committed `21` proof baseline is the right audit surface for the final-two question because Oracle’s conclusion was specifically about that state.
3. The search must reject any candidate that merely restates an earlier accepted source token key. That is the non-negotiable anti-cheating rule.
4. If the search finds nothing fresh, that is still progress: it converts the problem from “maybe more threshold tuning” into “receipt-construction/model/data problem with named divergent events.”

## Inline Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-04-29-factory2-overnight-final-two-to-goal.md`.

Executing inline tonight using `superpowers:executing-plans`, with this stopping rule:
- keep going until either:
  - a fresh proof source lineage is recovered for one or both final events, or
  - the repo contains an explicit, auditable divergence artifact proving why proof honestly stops short.
