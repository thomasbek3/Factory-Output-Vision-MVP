# Risks

Date: 2026-03-11

This file tracks the main migration risks and how to contain them.

## Risk 1 - UI Rewrite Breaks Working Operations

Why it matters:
- operators lose access to setup or monitoring during migration

Mitigation:
- keep old UI until React reaches parity
- cut over screen by screen, not all at once
- do not delete templates before verification

## Risk 2 - API Contract Drift

Why it matters:
- frontend breaks because backend payloads change shape during implementation

Mitigation:
- freeze request and response schemas first
- add typed frontend client
- version routes if needed without removing current ones

## Risk 3 - Reconnect Logic Regressions

Why it matters:
- live monitoring is less reliable after runtime changes

Mitigation:
- implement reconnect with explicit state transitions and events
- test frame stall, restart, and recovery behavior
- expose reconnect attempts in diagnostics

## Risk 4 - Silent Failures Hide Real Bugs

Why it matters:
- the system appears idle instead of visibly failing

Current concern:
`vision_worker.py` currently has exception swallowing in worker loops

Mitigation:
- replace silent catch blocks with logging and event emission
- surface latest error details in diagnostics

## Risk 5 - Data Model Changes Corrupt Existing DB

Why it matters:
- config or event history could be lost during schema expansion

Mitigation:
- use additive migrations
- test initialization on a clean DB
- test migration on the current `data/factory_counter.db`
- do not remove current tables or columns during the first pass

## Risk 6 - Coordinate Drift In The New Drawing UI

Why it matters:
- ROI and line data save incorrectly across different screen sizes

Mitigation:
- keep normalized coordinates
- isolate annotation math into one shared component
- verify reload accuracy at multiple viewport sizes

## Risk 7 - Frontend Build Integration Gets Messy

Why it matters:
- local dev and deployed appliance behavior diverge

Mitigation:
- choose one production model early
- recommended: React builds static assets, FastAPI serves them in production
- keep dev mode separate for speed

Current status:
- FastAPI now serves `frontend/dist` by default when present
- cutover routing is covered by automated tests for both React-first and legacy-forwarding cases

Residual concern:
- browser-driven frontend interaction tests are now present for core flows
- deeper failure-path browser coverage is still limited

## Risk 8 - Big-Bang Rewrite Slows Everything Down

Why it matters:
- too many moving parts change at once and nothing is trustworthy

Mitigation:
- backend hardening first
- frontend migration second
- tests before deletion
- keep each phase independently shippable

## Release Guardrails

Do not cut over to the new UI until:
- the core smoke test passes
- reconnect path is verified
- diagnostics path is verified
- setup, calibration, and monitoring work end to end
