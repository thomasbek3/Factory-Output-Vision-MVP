# Test Case Registry

The machine-readable registry is `validation/registry.json`.

## Status Values

- `verified_test_case`: promoted numbered case suitable as a canonical regression/demo target.
- `verified_candidate`: clean app proof exists, but it is not promoted to a numbered test case.
- `candidate`: work in progress.
- `archived`: historical evidence only.

## Current Entries

| Case ID | Status | Truth | Manifest |
| --- | --- | ---: | --- |
| `factory2_test_case_1` | `verified_test_case` | 23 | `validation/test_cases/factory2.json` |
| `img3262_candidate` | `verified_candidate` | 21 | `validation/test_cases/img3262.json` |
| `img3254_clean22_candidate` | `verified_candidate` | 22 | `validation/test_cases/img3254_clean22.json` |

## Required Manifest Evidence

Each manifest must include:

- Video path, SHA-256, duration, codec, width, and height.
- Truth rule ID, expected total, count rule, and truth ledger.
- Runtime settings: count mode, demo count mode, playback speed, FPS, model, calibration, and event parameters.
- Proof artifacts: observed app events, app-vs-truth comparison, pacing report when available, screenshots when available.
- Final validation report when available.
- Proof summary: observed total, matched count, missing count, unexpected count, first divergence, and wall/source pacing.

## Review Standard

If a future developer cannot reproduce the launch command and find the exact truth/comparison artifacts from the manifest, the entry is not complete.
