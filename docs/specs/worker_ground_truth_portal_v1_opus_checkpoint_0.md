# Worker Ground-Truth Portal - Opus Checkpoint 0

Date: 2026-07-25  
Checkpoint: specification contract before implementation  
Invocation: Claude Code `--model opus --effort high`, tool-less review  
Session receipt: `b2052347-9a1a-4e9a-99c5-e4bca58eb4c3`  
Initial verdict: **REVISE**

The CLI response did not expose a concrete model ID in its JSON result. This
receipt proves the requested `opus` alias and `high` effort flags were used; it
does not claim a more specific model identifier than the CLI returned.

## P0 Findings

1. Ops could both adjudicate and read AI comparison data, defeating the embargo.
2. Signed R2 delivery could not support the spec's claimed server-side
   byte-range corroboration.
3. The Spanish instruction did not use the same frame-anchored physical event as
   the resolver.
4. Five-minute onboarding was arithmetically impossible with two 15-minute
   training chunks and MFA.
5. Hidden golden replay provenance and owner publication behavior were
   undefined.
6. Golden, speed, and audit thresholds could not reach statistical resolution at
   pilot volume.
7. `Verified through` was undefined across quarantined or unusable gaps.
8. End-of-shift and quarantined-partner seams had no terminal state.
9. The spec asserted three-account independence without preventing one person or
   device from operating multiple reviewer accounts on the same chunk.

## Required Corrections Applied

- Added a single capability matrix: Ops, adjudicator, and AI analyst are
  disjoint.
- Removed false server-corroboration language for direct signed-object delivery.
  Coverage is unverified telemetry plus a weak per-assignment elapsed-time
  sanity floor.
- Added one bilingual release-and-remains frame anchor and versioned station
  lexicon contract.
- Replaced onboarding with 90-second practice/qualification clips and a
  5-minute-to-practice / 15-minute-to-real-work budget including TOTP MFA.
- Replaced hidden replay golden work with explicit qualification clips and
  post-hoc audits of normally displayed production chunks.
- Replaced statistically unsupported percentage gates with sample floors,
  zero-miss checks, Wilson intervals, and pre-registered power requirements.
- Defined contiguous verified-through semantics and explicit unverified gaps.
- Added end-of-shift and quarantined-partner seam terminal states.
- Added invite identity proofing, registered-device exclusion, shared-network
  controls, and cross-submission similarity checks.
- Split proof into Tier A local/CI, Tier B real-footage/hardware, and Tier C
  pilot/legal acceptance.
- Marked zero-offset/index-derived helpers in `reviewChunks.ts` for deletion.
- Reopened the prior Fable disposition instead of self-certifying it as closed.

## Re-Review Gate

Checkpoint zero is not passed by this document. A fresh independent Fable pass
and a fresh Opus high-effort pass must return no open P0 before Phase 1 code.
