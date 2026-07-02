# ADR 0004: Live Overhead Station Uses Clip Action Recognition, Not Object Detection

Status: Accepted (evaluation lane; promotion pending the blind exam gate)

Date: 2026-06-13

## Context

ADR 0001 makes the YOLO/event runtime the system of record, and it holds for the
boxable test cases (Factory2, IMG_3262/3254/2628), which validate cleanly.

The live overhead factory station is different. It is a fixed overhead camera over
a welding/output bench, and the finished product is thin wire-lattice frames. On
this station YOLO object detection failed unambiguously:

- The day-2 trained detector scored 0/7 on the blind exam and 0% recall on its own
  12 training images (`cls_loss` stuck ~4.2, mAP 0).
- The product is unboxable from overhead, verified three ways: the output pile is
  an indistinguishable lattice; the carried frame merges into the worker's body
  even when zoomed; "the newest placed frame" is not visually separable in a still.

The discriminative signal is the action over time (carry → place → leave), which a
human and the Codex teacher read correctly from the same footage that defeats a box
detector. Independent research (deep-research workflow + a separate Codex review)
confirmed this is how Drishti — a manufacturing video-AI company, acquired by Apple
in 2023 — solved counting at manual stations: action recognition, never boxing the
part.

## Decision

For the **live overhead station only**, the runtime student is a **clip
action-recognition model**, not an object detector:

```text
fixed camera
  -> zone tripwire (cheap pixel change detector; high recall, no AI)
  -> per-candidate clip (before / during / after of the output zone)
  -> small video model: placement? yes / no
  -> debounced state-machine counter
```

Teacher labels (Codex + human) are produced at training time only; the small model
runs live with no teacher in the loop. This change is scoped to the live station;
it does not retire YOLO for the already-validated boxable cases (ADR 0001 stands
for those). It plugs into the existing counting/validation contracts rather than
introducing a separate vendor workflow, consistent with ADR 0001's "extend through
narrow interfaces" direction. Until it passes the validation gate it is an
evaluation lane under ADR 0003.

## Consequences

- The live-station detector family changes from object detection to action
  recognition; the dashboard, counting semantics, and validation registry contracts
  are preserved.
- Labeling shifts from bounding boxes to whole-clip judgments. The teacher/advisory
  boundary is unchanged: teacher labels are bronze/pending, never live truth.
- A tracked held-out truth artifact exists for this station: 7 human+Codex-verified
  placements (`validation/exam/exam_gold_positives.json`) that must never enter
  any training set.
- Build artifacts live on branch `day4-action-recognition`; the implementation spec
  is `docs/specs/day4_action_recognition_spec.md`.
- YOLO research/experiments for this station move to an evaluation lane (ADR 0003);
  they are not the runtime path.

## Verification Gate

Promotion of the action-recognition runtime for the live station requires:

- Tripwire recall ≥ 6/7 on the held-out exam hour. (Met: 7/7 on 2026-06-13.)
- The trained clip model passes the blind exam (`scripts/run_clip_exam.py`): all 7
  placements matched, 0 false counts, no training on the held-out 7.
- Real app-path proof at `1.0x` before any field/runtime claim.
- A live-camera (RTSP) validation before any Reolink/field claim.
- Updated architecture docs and this ADR's status moved from evaluation to promoted.
