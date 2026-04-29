# Factory2 Synthetic Lineage Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the remaining Factory2 proof/runtime mismatch by determining whether `synthetic_approved_chain_token` events can be converted into honest live-token lineage counts without false positives, and if so ship that bounded fix; otherwise preserve runtime `23` while explicitly finalizing proof `21` as the honest audit ceiling.

**Architecture:** Start from the already-pushed lineage baseline: one-pass runtime counts `23`, proof counts `21`, and the unresolved events are synthetic approved-delivery-chain counts. Build a deterministic lineage analysis report first, then only ship a runtime/state-machine change if the report shows the final synthetic counts are recoverable via bounded long-gap source lineage retention instead of loose token reuse. Keep proof receipts and runtime provenance separate until the data says they can converge honestly.

**Tech Stack:** Python 3.9, pytest, existing Factory2 runtime counter and proof scripts, JSON artifacts under `data/reports/` and `data/diagnostics/`, repo `.venv` for video and vision dependencies.

---

## File Map

**Create**

- `docs/superpowers/plans/2026-04-29-factory2-synthetic-lineage-convergence.md`
- `scripts/build_factory2_synthetic_lineage_report.py`
- `tests/test_build_factory2_synthetic_lineage_report.py`

**Likely modify if analysis supports a fix**

- `app/services/count_state_machine.py`
- `app/services/runtime_event_counter.py`
- `scripts/audit_factory2_runtime_events.py`
- `tests/test_count_state_machine.py`
- `tests/test_runtime_event_counter.py`
- `tests/test_audit_factory2_runtime_events.py`
- `.hermes/HANDOFF.md`
- `AGENTS.md`
- `CLAUDE.md`
- `tasks/lessons.md`

**Locked baseline artifacts**

- `data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json`
- `data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json`
- `data/reports/factory2_proof_runtime_divergence.final_two_v2.json`

**New output artifacts**

- `data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json`
- optionally, if a guarded fix is safe:
  - `data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json`
  - `data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v3.json`
  - `data/reports/factory2_proof_runtime_divergence.final_two_v3.json`

---

## Starting Truth

This plan is anchored to the current repo state:

- runtime/app one-pass result: `23`
- proof result: `21`
- remaining divergent runtime events:
  - `305.708s`
  - `425.012s`
- both currently classify as:
  - `reason = approved_delivery_chain`
  - `provenance_status = synthetic_approved_chain_token`

That means the old problem statement is obsolete. The question is not “how do we find two more windows.” The question is:

```text
Are the final synthetic counts recoverable because the source token died too early during a real long-gap carry,
or are they synthetic because runtime is currently granting count authority beyond what honest source lineage supports?
```

Only the first answer justifies more code.

---

## Decision Gate

Before touching runtime semantics, the analysis report must prove all of these:

1. The unresolved synthetic counts have a predecessor chain that begins with real source-zone evidence.
2. The chain gap is bounded and explainable as occlusion or tracker fragmentation, not arbitrary inactivity.
3. No already-counted event consumed the same source-lineage authority.
4. A bounded token-retention rule can recover those events without widening count authority globally.

If any of those fail, do not “make proof say 23” and do not loosen thresholds. Finalize the honest divergence instead.

---

### Task 1: Build A Synthetic-Lineage Analysis Report

**Files:**
- Create: `scripts/build_factory2_synthetic_lineage_report.py`
- Create: `tests/test_build_factory2_synthetic_lineage_report.py`
- Inputs:
  - `data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json`
  - `data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json`
  - `data/reports/factory2_proof_runtime_divergence.final_two_v2.json`
- Output:
  - `data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json`

- [ ] **Step 1: Write the failing test**

```python
import json

from scripts.build_factory2_synthetic_lineage_report import build_synthetic_lineage_report


def test_build_synthetic_lineage_report_groups_events_by_provenance(tmp_path) -> None:
    runtime_path = tmp_path / "runtime.json"
    proof_path = tmp_path / "proof.json"
    divergence_path = tmp_path / "divergence.json"
    output_path = tmp_path / "report.json"
    runtime_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_ts": 100.0,
                        "track_id": 11,
                        "reason": "approved_delivery_chain",
                        "source_track_id": 7,
                        "source_token_id": "source-token-1",
                        "provenance_status": "synthetic_approved_chain_token",
                    },
                    {
                        "event_ts": 120.0,
                        "track_id": 12,
                        "reason": "approved_delivery_chain",
                        "source_track_id": 8,
                        "source_token_id": "source-token-2",
                        "provenance_status": "inherited_live_source_token",
                    },
                ],
                "track_histories": {
                    "7": [
                        {"timestamp": 90.0, "zone": "source"},
                        {"timestamp": 91.0, "zone": "source"},
                    ],
                    "11": [{"timestamp": 100.0, "zone": "output"}],
                },
            }
        ),
        encoding="utf-8",
    )
    proof_path.write_text(json.dumps({"accepted_count": 21}), encoding="utf-8")
    divergence_path.write_text(
        json.dumps(
            {
                "divergent_events": [
                    {
                        "event_ts": 100.0,
                        "proof_blocker": "synthetic_approved_chain_token",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_synthetic_lineage_report(
        runtime_audit_path=runtime_path,
        proof_report_path=proof_path,
        divergence_path=divergence_path,
        output_path=output_path,
        force=True,
    )

    assert payload["approved_delivery_chain_count"] == 2
    assert payload["synthetic_count"] == 1
    assert payload["inherited_live_count"] == 1
    assert payload["divergent_synthetic_count"] == 1
    assert payload["synthetic_events"][0]["source_gap_seconds"] == 9.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_factory2_synthetic_lineage_report.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing `build_synthetic_lineage_report`.

- [ ] **Step 3: Write minimal implementation**

```python
def source_gap_seconds(event: dict[str, Any], track_histories: dict[str, list[dict[str, Any]]]) -> float | None:
    source_track_id = event.get("source_track_id")
    if source_track_id is None:
        return None
    source_history = track_histories.get(str(source_track_id)) or []
    if not source_history:
        return None
    last_source_ts = max(float(row["timestamp"]) for row in source_history)
    return round(float(event["event_ts"]) - last_source_ts, 3)
```

```python
def build_synthetic_lineage_report(
    *,
    runtime_audit_path: Path,
    proof_report_path: Path,
    divergence_path: Path,
    output_path: Path,
    force: bool,
) -> dict[str, Any]:
    runtime = json.loads(runtime_audit_path.read_text(encoding="utf-8"))
    divergence = json.loads(divergence_path.read_text(encoding="utf-8"))
    divergent_ts = {
        round(float(row["event_ts"]), 3)
        for row in (divergence.get("divergent_events") or [])
    }
    events = [
        row
        for row in (runtime.get("events") or [])
        if row.get("reason") == "approved_delivery_chain"
    ]
    track_histories = runtime.get("track_histories") or {}
    synthetic_events = []
    inherited_events = []
    for row in events:
        enriched = dict(row)
        enriched["source_gap_seconds"] = source_gap_seconds(row, track_histories)
        enriched["is_divergent"] = round(float(row["event_ts"]), 3) in divergent_ts
        if row.get("provenance_status") == "synthetic_approved_chain_token":
            synthetic_events.append(enriched)
        else:
            inherited_events.append(enriched)
    payload = {
        "schema_version": "factory2-synthetic-lineage-report-v1",
        "approved_delivery_chain_count": len(events),
        "synthetic_count": len(synthetic_events),
        "inherited_live_count": len(inherited_events),
        "divergent_synthetic_count": sum(1 for row in synthetic_events if row["is_divergent"]),
        "synthetic_events": synthetic_events,
        "inherited_events": inherited_events,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_factory2_synthetic_lineage_report.py -q`
Expected: PASS

- [ ] **Step 5: Generate the real report**

Run:

```bash
.venv/bin/python scripts/build_factory2_synthetic_lineage_report.py \
  --runtime-audit /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json \
  --proof-report /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json \
  --divergence /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_proof_runtime_divergence.final_two_v2.json \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json \
  --force
```

Expected:

```text
approved_delivery_chain_count > 0
synthetic_count >= 2
divergent_synthetic_count == 2
```

- [ ] **Step 6: Commit**

```bash
git add scripts/build_factory2_synthetic_lineage_report.py \
  tests/test_build_factory2_synthetic_lineage_report.py \
  data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json
git commit -m "feat: add factory2 synthetic lineage report"
```

---

### Task 2: Extend Runtime Audit Rows With Predecessor-Chain Context

**Files:**
- Modify: `scripts/audit_factory2_runtime_events.py`
- Modify: `tests/test_audit_factory2_runtime_events.py`
- Reuse:
  - `app/services/runtime_event_counter.py`
- Output impact:
  - future runtime audits include chain members and source/output observation counts

- [ ] **Step 1: Write the failing test**

```python
def test_serialize_event_includes_predecessor_chain_context() -> None:
    event = CountEvent(
        track_id=12,
        count=1,
        reason="approved_delivery_chain",
        bbox=(10.0, 20.0, 30.0, 40.0),
        source_track_id=7,
        source_token_id="source-token-1",
        chain_id="proof-source-track:7",
        provenance_status="synthetic_approved_chain_token",
    )
    gate = SimpleNamespace(decision="allow_source_token", reason="moving_panel_candidate", flags=["x"])
    payload = serialize_event(
        event_ts=120.0,
        event=event,
        gate_decision=gate,
        count_total=3,
        provenance={
            "predecessor_chain_track_ids": [5, 7, 12],
            "source_observation_count": 22,
            "output_observation_count": 2,
        },
    )

    assert payload["predecessor_chain_track_ids"] == [5, 7, 12]
    assert payload["source_observation_count"] == 22
    assert payload["output_observation_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit_factory2_runtime_events.py::test_serialize_event_includes_predecessor_chain_context -q`
Expected: FAIL because `serialize_event()` does not accept or emit provenance context.

- [ ] **Step 3: Write minimal implementation**

```python
def serialize_event(
    *,
    event_ts: float,
    event: CountEvent,
    gate_decision: Any,
    count_total: int,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = provenance or {}
    return {
        ...
        "predecessor_chain_track_ids": list(provenance.get("predecessor_chain_track_ids") or []),
        "source_observation_count": int(provenance.get("source_observation_count") or 0),
        "output_observation_count": int(provenance.get("output_observation_count") or 0),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit_factory2_runtime_events.py::test_serialize_event_includes_predecessor_chain_context -q`
Expected: PASS

- [ ] **Step 5: Rebuild the real runtime audit if the report needs this context**

Run:

```bash
.venv/bin/python scripts/audit_factory2_runtime_events.py \
  --video /Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV \
  --calibration /Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json \
  --model /Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json \
  --start-seconds 0 --end-seconds 430 --processing-fps 10 \
  --include-track-histories --force
```

Expected: the runtime audit rows for `305.708s` and `425.012s` now show explicit predecessor-chain membership and per-side observation counts.

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_factory2_runtime_events.py tests/test_audit_factory2_runtime_events.py \
  data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json
git commit -m "feat: enrich factory2 runtime audit lineage context"
```

---

### Task 3: Decide Whether A Guarded Long-Gap Source Hold Is Legitimate

**Files:**
- Read:
  - `data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json`
  - optionally `data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json`
- No code unless the decision criteria pass

- [ ] **Step 1: Read the real synthetic-lineage report**

Look for:

```text
- how many synthetic approved-delivery-chain events exist total
- which synthetic events are already independently proof-recovered
- whether the final two are outliers or typical
- source_gap_seconds for the final two
- whether predecessor chains begin with real source observations
```

- [ ] **Step 2: Evaluate the decision gate**

Pass only if:

```text
- the final two have bounded predecessor chains
- the gap is long but finite and not obviously arbitrary
- no already-counted event consumed the same source-lineage authority
- the synthetic events that proof already recovered look structurally similar
```

Fail if:

```text
- source_track evidence is only a one-frame stub
- the chain gap is too long and unanchored
- the same lineage already produced a committed count
- the proposed retention would effectively mint new authority
```

- [ ] **Step 3: Choose the branch**

Branch A:

```text
Guarded long-gap retention is safe -> implement Task 4.
```

Branch B:

```text
Guarded long-gap retention is not safe -> skip Task 4, update doctrine and handoff, and stop claiming proof can converge honestly on the current evidence.
```

---

### Task 4: Implement Guarded Long-Gap Source-Lineage Retention

**Only execute this task if Task 3 passes.**

**Files:**
- Modify: `app/services/count_state_machine.py`
- Modify: `app/services/runtime_event_counter.py`
- Modify: `tests/test_count_state_machine.py`
- Modify: `tests/test_runtime_event_counter.py`

**Implementation target:**

Convert eligible synthetic approved-delivery-chain events into inherited live-source-token events only when:

- the chain was gate-approved
- the earliest predecessor had real source-zone evidence
- the source authority has not already been consumed
- the output appears within a bounded approved-chain gap
- the hold is scoped to that chain, not global idle time

- [ ] **Step 1: Write the failing count-state-machine test**

```python
def test_commit_approved_delivery_chain_can_inherit_reserved_source_token_after_long_gap() -> None:
    counter = CountStateMachine(
        CountConfig(
            zones=make_test_zones(),
            source_token_ttl_frames=45,
        )
    )
    source = counter._tracks.setdefault(10, _TrackMemory(track_id=10))
    source.source_token = _SourceToken(
        token_id="source-token-1",
        track_id=10,
        created_frame=1,
        last_frame=10,
        source_bbox=(100.0, 100.0, 40.0, 40.0),
    )
    counter.register_reserved_chain_source_token(
        chain_id="proof-source-track:10",
        source_track_id=10,
        source_token_id="source-token-1",
        source_bbox=(100.0, 100.0, 40.0, 40.0),
        last_source_frame=10,
        max_gap_frames=120,
    )
    counter._frame_index = 95

    event = counter.commit_approved_delivery_chain(
        chain_id="proof-source-track:10",
        source_track_id=10,
        output_track_id=20,
        output_bbox=(400.0, 400.0, 40.0, 40.0),
    )

    assert event is not None
    assert event.provenance_status == "inherited_reserved_source_token"
    assert event.source_token_id == "source-token-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_count_state_machine.py::test_commit_approved_delivery_chain_can_inherit_reserved_source_token_after_long_gap -q`
Expected: FAIL because reserved chain token support does not exist.

- [ ] **Step 3: Write the failing runtime-counter guard test**

```python
def test_runtime_event_counter_does_not_reserve_unapproved_chain_tokens() -> None:
    counter = RuntimeEventCounter(zones=make_test_zones(), gate=None, tracker_match_distance=80.0)
    # set up a source-side predecessor and an output-only fragment that never passes the gate
    # expectation: no reserved source token is registered and no count is emitted
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_runtime_event_counter.py::test_runtime_event_counter_does_not_reserve_unapproved_chain_tokens -q`
Expected: FAIL

- [ ] **Step 5: Write minimal implementation**

Implement a bounded reservation path:

```python
@dataclass
class _ReservedChainSourceToken:
    chain_id: str
    source_track_id: int
    source_token_id: str
    source_bbox: Box
    last_source_frame: int
    max_gap_frames: int
    consumed: bool = False
```

Rules:

```text
- create reservation only for gate-approved predecessor chains
- reservation references an existing real source token; it does not create one
- reservation expires after max_gap_frames
- reservation can be consumed exactly once
- reservation never overrides an already-counted source token
```

- [ ] **Step 6: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_count_state_machine.py \
  tests/test_runtime_event_counter.py \
  tests/test_audit_factory2_runtime_events.py -q
```

Expected: PASS on new and existing delivery-chain tests.

- [ ] **Step 7: Run the real no-loop audit**

Run:

```bash
.venv/bin/python scripts/audit_factory2_runtime_events.py \
  --video /Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV \
  --calibration /Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json \
  --model /Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt \
  --output /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json \
  --start-seconds 0 --end-seconds 430 --processing-fps 10 \
  --include-track-histories --force
```

Expected:

```text
final_count stays 23
the final two no longer appear as synthetic_approved_chain_token if the fix is legitimate
no new duplicate counts appear
```

- [ ] **Step 8: Commit**

```bash
git add app/services/count_state_machine.py app/services/runtime_event_counter.py \
  tests/test_count_state_machine.py tests/test_runtime_event_counter.py \
  tests/test_audit_factory2_runtime_events.py \
  data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json
git commit -m "feat: add guarded factory2 long-gap source lineage retention"
```

---

### Task 5: Rebuild Proof And Decide End State

**Files:**
- Modify if needed: `scripts/build_morning_proof_report.py`
- Modify: `.hermes/HANDOFF.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `tasks/lessons.md`

- [ ] **Step 1: Rebuild proof artifacts**

Run:

```bash
.venv/bin/python scripts/build_factory2_runtime_lineage_diagnostic.py \
  --runtime-audit /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json \
  --event-ts 305.708 \
  --output-dir /Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/runtime-proof/factory2-runtime-only-0007-lineage-v3 \
  --force

.venv/bin/python scripts/build_factory2_runtime_lineage_diagnostic.py \
  --runtime-audit /Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.lineage_0_430.v3.json \
  --event-ts 425.012 \
  --output-dir /Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/runtime-proof/factory2-runtime-only-0008-lineage-v2 \
  --force
```

Then rebuild:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.build_morning_proof_report import build_morning_proof_report

build_morning_proof_report(
    diagnostic_paths=[
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/runtime-proof/factory2-runtime-only-0007-lineage-v3/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/runtime-proof/factory2-runtime-only-0008-lineage-v2/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0019-000-010s-panel-v1-8fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0000-000-078s-panel-v2-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0006-058-099s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0012-145-185s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0008-232-272s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0016-274-294s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0009-332-372s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0011-372-412s-panel-v1-5fps/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0005-396-427s-panel-v2/diagnostic.json"),
        Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/diagnostics/event-windows/factory2-review-0005-418s-panel-v1/diagnostic.json"),
    ],
    output_path=Path("/Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v3.json"),
)
PY
```

- [ ] **Step 2: Evaluate the result**

Success:

```text
runtime remains 23
proof rises above 21 honestly
ideally proof reaches 23 with no threshold loosening
```

Fallback:

```text
runtime remains 23
proof remains 21
the two events still classify as synthetic or lineage-incomplete
```

- [ ] **Step 3: Update doctrine and handoff**

If success:

```text
- document the guarded long-gap lineage rule
- state that runtime/proof now converge
```

If fallback:

```text
- document that guarded retention was rejected or insufficient
- state explicitly that runtime 23 / proof 21 is still the honest state
```

- [ ] **Step 4: Run verification**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_count_state_machine.py \
  tests/test_runtime_event_counter.py \
  tests/test_audit_factory2_runtime_events.py \
  tests/test_build_factory2_runtime_lineage_diagnostic.py \
  tests/test_build_morning_proof_report.py \
  tests/test_build_factory2_synthetic_lineage_report.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/HANDOFF.md AGENTS.md CLAUDE.md tasks/lessons.md \
  data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v3.json \
  data/reports/factory2_proof_runtime_divergence.final_two_v3.json
git commit -m "feat: finalize factory2 synthetic lineage convergence"
```

---

## Self-Review

**Spec coverage:** This plan covers the real remaining problem after the lineage audit: analyzing synthetic approved-delivery-chain events, deciding whether long-gap lineage retention is legitimate, implementing it only if bounded and safe, and rerunning runtime plus proof.

**Placeholder scan:** There are no `TODO` or `TBD` placeholders. The branch point is explicit and intentional: Task 4 executes only if Task 3 passes the decision gate.

**Type consistency:** The plan consistently uses:

- `provenance_status`
- `approved_delivery_chain`
- `synthetic_approved_chain_token`
- `inherited_live_source_token`
- `source_token_id`
- `source_track_id`
- `chain_id`

The proposed new reserved-token path uses one new label consistently:

- `inherited_reserved_source_token`

---

## Execution Mode

This plan is being executed inline in the current session using `superpowers:executing-plans`, because the user explicitly asked for overnight autonomous execution rather than a pause for choice.
