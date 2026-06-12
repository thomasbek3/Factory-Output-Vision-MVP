# Architecture Decision Records

This folder contains durable architecture decisions.

Use an ADR when a change would otherwise be rediscovered or reargued later.

## Format

Each decision should include:

- status
- date
- context
- decision
- consequences
- verification or promotion gate

## Records

| ADR | Decision |
| --- | --- |
| `0001-current-runtime-is-system-of-record.md` | Keep the existing app runtime as source of truth |
| `0002-validation-registry-is-promotion-gate.md` | Use the validation registry as the promotion gate |
| `0003-detector-and-edge-stack-changes-are-evaluation-lanes.md` | Keep detector/hardware/vendor stack changes behind benchmark gates |
| `0004-vlm-and-teacher-models-are-audit-only.md` | Keep VLMs and teacher models out of live count authority |
