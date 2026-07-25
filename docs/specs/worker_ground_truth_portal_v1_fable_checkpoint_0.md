# Worker Ground-Truth Portal v1 - Fable Checkpoint 0

Date: 2026-07-25

## Review receipt

- Reviewer alias requested: `fable`
- Resolved model reported by Claude CLI: `claude-fable-5`
- Effort: `high`
- Session: `a3c58cac-4b90-4a32-95c0-801ff759dbed`
- Reported turns: 26
- Initial closure verdict: **REVISE**

The first two bounded attempts ended without a report: one exhausted the
agentic-turn limit and one received a server error. Neither was counted as a
review. The receipt above is the completed independent review.

## Findings and disposition

The review reopened one P0: `app_spec_v1.md` still mandated one-click verified
events, hidden golden injection, worker throughput metrics, second-review wins,
and a `10x` default. A dated amendment now defers reviewer and verification
behavior to the worker-portal spec and removes those conflicting requirements.

The review also identified:

- padded rendition context could expose an adjacent exam interval;
- the verification-copy CI guard was too narrow;
- one adjudication paragraph weakened the absolute AI embargo;
- leading and trailing Spanish context needed different copy;
- the Spanish event anchor omitted `finished` and `frame`;
- re-encoded footage needed declared lineage for source-set isolation;
- empty Tier B source sets and not-yet-implemented registry consumers needed
  more honest language.

Each item above was corrected in the checkpoint-zero change set and is covered
by contract or unit tests where Tier A proof is possible.

## Closure status

**OPEN** until a fresh Fable pass and a fresh Opus high-effort pass both return
no open P0 after the amendment commit hash is recorded.

## Second closure pass

- Resolved model: `claude-fable-5`
- Effort: `high`
- Session: `bddc1715-62f9-46b6-9b4f-49229756a04f`
- Reported turns: 20
- Verdict: **REVISE**

This pass found that the first dated amendment was too narrow. Named-reviewer
copy and model evidence still survived in the locked replay, ClipDrawer, and Ops
contracts and in two owner-facing components. The amendment now covers every
verification/identity/model-evidence requirement in the app spec and design
contract; the components now label fixture evidence as seeded review and expose
neither reviewer identity nor model output.

The same pass also led to cross-registry exam containment, same-set duplicate
rejection, explicit clipped presentation intervals, Spanish `+1 PIEZA` copy,
and separate non-audited/audited publication-latency cohorts.

## Third closure pass

- Resolved model: `claude-fable-5`
- Effort: `high`
- Session: `80e9a9de-aa82-4292-bfba-24e5724a9012`
- Reported turns: 23
- Verdict: **PASS**

Fable verified that all nine prior Opus P0 findings and all six original Fable
minimum changes are closed. Its remaining P1/P2 findings were remediated before
the Opus gate:

- holdout-to-firewall containment is now bidirectional;
- different source sets enforce a five-second context isolation margin;
- missing contract files and an empty owner-component scan fail explicitly;
- assignment/presentation timestamps must be timezone-aware UTC;
- seam-dependent chunks have a separate latency cohort.

Fresh local evidence after those changes:

- focused firewall/source-set/copy contract tests: `23 passed`;
- complete backend suite: `644 passed`, with 16 dependency warnings;
- repository docs/hygiene check: passed;
- `git show 723df77054289be5e0f9992b97b0817f76bf4621` confirms the widened
  amendment includes both `DESIGN.md` and `docs/specs/app_spec_v1.md`.

Fable checkpoint status: **PASS**. Tier B and Tier C evidence remains explicitly
blocked and is not represented as completed.
