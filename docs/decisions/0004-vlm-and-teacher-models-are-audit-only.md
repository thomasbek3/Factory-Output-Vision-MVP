# ADR 0004: VLM And Teacher Models Are Audit Only

Status: Accepted

Date: 2026-06-04

## Context

Vision-language models and teacher models can help review ambiguous events, label training data, and explain failures. They are not reliable live count authorities for this product. The repository already separates live runtime count from active-learning and review outputs.

## Decision

VLMs, teacher models, Moondream, Cosmos Reason2, and similar systems are offline/advisory only.

They may produce:

- review suggestions
- flagged-cycle explanations
- training candidates
- support-bundle summaries
- learning-library evidence

They may not increment Runtime Total, rewrite validation truth, or silently upload footage.

## Consequences

- Live counting remains local and deterministic through the app path.
- Teacher labels start as advisory/pending labels.
- Gold validation truth requires human/reconciled verification.
- Cloud-assisted audit or labeling requires explicit permission.

## Verification Gate

Any runtime path that calls a VLM before incrementing count violates this ADR unless a future ADR explicitly changes count authority.
