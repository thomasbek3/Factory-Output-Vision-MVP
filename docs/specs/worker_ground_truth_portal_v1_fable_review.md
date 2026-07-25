# Worker Ground-Truth Portal v1 - Fable Review

Date: 2026-07-25  
Method: independent unknown-unknowns pass  
Framework: Thariq Shihipar, "A Field Guide to Fable: Finding Your Unknowns"  
Artifact reviewed: `worker_ground_truth_portal_v1.md` plus current reviewer,
runtime, security, storage, design, schema, API, and test files  
Initial verdict: **REVISE**  
Disposition: minimum changes were incorporated, then reopened after the
checkpoint-zero Opus review found three closures were incomplete. See
`worker_ground_truth_portal_v1_opus_checkpoint_0.md`.

Correction note (2026-07-25): the portal spec does not unilaterally supersede
the locked design and app contracts. Both require an explicit dated amendment;
the later contract amendment, rather than the draft alone, closes that copy
conflict.

## What Fable Confirmed

The original draft correctly identified the production gaps in the current demo:
client-supplied reviewer identity, in-memory persistence, one-review completion,
golden-answer exposure, peer-count leakage, and the absence of assignment,
submission, consensus, adjudication, and AI-run entities.

## Unknown Knowns

Fable surfaced assumptions that were present in the design but not explicit:

- Three reviews require a reviewer pool larger than three.
- Traversed video is not necessarily perceived video, especially at 10x-15x.
- High-speed playback needs both bandwidth and device decode capacity.
- Transcoded media must preserve a measurable mapping to source time.
- Reviewer compensation changes fraud and quality incentives.
- Factory authorization is legally distinct from notice/consent for filmed
  employees.
- Three unanimous reviewers can share the same correlated blind spot.

## Unknown Unknowns

Ranked blind spots:

1. **Chunk seams:** a placement could be counted in both adjacent chunks or
   neither.
2. **Spoofable coverage:** client coverage telemetry was carrying more authority
   than the trust model permitted.
3. **Procedural AI blindness:** ops/adjudicator role overlap could reveal AI
   results before a human decision.
4. **Screen-recording exposure:** signed URLs do not prevent a worker from
   recording the screen.
5. **Model deletion:** deleting footage and labels does not remove their
   influence from trained weights.
6. **Locked-copy conflict:** the design contract required "verified ... live"
   while the product actually publishes delayed human verification.

## Minimum Changes Requested And Disposition

| Fable request | Spec disposition |
| --- | --- |
| Resolve three-person roster deadlock | Uses five as a minimum planning floor, then sizes the final pool from measured p95 handle time and replacement/fourth-review demand |
| Treat coverage as untrusted | Explicitly removes the impossible server-corroboration claim for direct signed media; coverage is unverified telemetry supported by a weak elapsed-time guard, audits, and independence controls |
| Define chunk-boundary correctness | Added padded context, half-open ownership, cross-chunk seam dedup, and exact-once tests |
| Gate speed on real proof | Pilot starts at 5x; 10x/15x require golden miss-rate, dropped-frame, time-mapping, device, and bandwidth gates |
| Add bandwidth, latency, adjudication, and cost physics | Added formulas, headroom limits, review triggers, and a Thomas-approved cost ceiling gate |
| Structurally preserve blind AI review | Added mutually exclusive adjudicator/AI roles and API/database embargo tests |
| Expand legal/privacy/model deletion posture | Added filmed-employee basis, cross-border review, watermark/residual risk, and trained-weight deletion policy |
| Fix design-copy contradiction | This spec explicitly supersedes the dishonest live-verification copy and requires Phase 0 contract updates |

## Required Failure Tests

- One absent reviewer plus replacement and fourth-review request.
- Fabricated coverage and clicks without real media access.
- Sub-second placements at each candidate playback speed on real hardware.
- Placements immediately before, at, and after a 15-minute boundary.
- An adjudicator requesting AI data for an open case.
- Burned-timecode constant- and variable-frame-rate transcodes.

## Review State

The initial verdict remains recorded as `REVISE`. Checkpoint zero requires a
fresh Fable pass and a fresh Opus pass after the reopened coverage, seam,
role-separation, and correlated-human-error findings are corrected. Engineering
must still prove the measurable gates with real pilot footage, devices,
networks, staffing, and legal approval.
