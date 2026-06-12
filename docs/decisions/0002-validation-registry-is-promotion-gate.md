# ADR 0002: Validation Registry Is The Promotion Gate

Status: Accepted

Date: 2026-06-04

## Context

Factory Vision has multiple evidence types: raw footage, diagnostic reports, review queues, model training outputs, teacher/VLM labels, app events, and app-vs-truth comparisons. Without a gate, diagnostic success can be mistaken for product proof.

## Decision

`validation/registry.json` and `validation/test_cases/*.json` define promotion truth.

A case, model, detector, or settings profile is not promoted until it has:

- reviewed truth
- observed app events
- app-vs-truth comparison
- pacing evidence
- clean registry entry
- no teacher/VLM labels used as validation truth

## Consequences

- Diagnostic artifacts remain useful but cannot create product claims by themselves.
- New detectors and settings must prove timing and totals, not just final counts.
- Failed cases route to the learning registry instead of being forced into promotion.

## Verification Gate

Promotion requires:

```text
matched_count == expected_total
missing_truth_count == 0
unexpected_observed_count == 0
first_divergence == null
wall/source pacing near 1.0
```

Live Reolink/RTSP field proof requires the same discipline on an actual live camera stream.
