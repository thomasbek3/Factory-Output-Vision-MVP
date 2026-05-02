# Factory Vision Validation Registry

This directory contains the productized validation surface.

## Files

- `registry.json`: index of verified test cases and candidates.
- `test_cases/*.json`: per-video manifests with truth, runtime settings, proof artifacts, and proof summary.
- `schemas/*.schema.json`: JSON Schemas for validation artifacts.

## Workflow

```bash
.venv/bin/python scripts/validate_video.py --case-id img3254_clean22_candidate --dry-run
.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3254_clean22.json --force
```

The registry is not a substitute for proof. It points to proof artifacts that must remain reviewable.
