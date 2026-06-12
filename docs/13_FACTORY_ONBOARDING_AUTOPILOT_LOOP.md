# Factory Onboarding Autopilot Loop

Updated: 2026-06-08

## Purpose

This loop turns the recorded-buffer onboarding plan into repeatable work:

```text
RTSP/file input
  -> local segment recorder
  -> onboarding state machine
  -> teacher/calibration artifacts
  -> optional station detector training
  -> blind replay gate
  -> live YOLO/event counting
  -> periodic audit loop
```

The loop exists so agents do not prompt themselves vaguely. Each tick must pick
one milestone, implement the smallest useful slice, run its verifier, and either
fix, checkpoint, or stop for a real product decision.

## Count Authority

Live `Runtime Total` remains owned by the existing YOLO/event runtime. Teacher
models, VLMs, YOLOE, Cosmos, and periodic audits can create calibration
candidates, silver labels, dispute packets, and retraining triggers. They must
not increment, decrement, or silently rewrite live counts.

## Loop Tick

```text
1. Read AGENTS.md and current source-of-truth docs.
2. Read the current loop/milestone state.
3. Pick the next incomplete milestone.
4. Implement only that slice.
5. Run the slice verifier.
6. If verifier fails, fix and rerun.
7. If verifier passes, record evidence paths.
8. Run Codex review at checkpoint milestones.
9. Stop on no-progress, budget, risky count-authority changes, or product decisions.
```

## Milestones And Verifiers

| Milestone | Build | Required verifier |
| --- | --- | --- |
| M1 | Segment recorder sidecar | file/RTSP command tests, segment manifest tests, retention/pin tests |
| M2 | Segment manifest persistence | schema tests, pinned chunks never deleted |
| M3 | Onboarding state machine | dry-run session fails closed without real teacher output |
| M4 | Candidate-window extraction | recorded chunks produce positive, idle, worker, and hard-negative windows |
| M5 | Teacher provider contract | dry-run and fake-teacher tests; no cloud by default |
| M6 | Calibration artifact | `station_calibration.json` validates and app can load it |
| M7 | YOLO26 training runner | train/eval reports on positives and hard negatives |
| M8 | Blind replay gate | held-out chunk runs through actual app runtime and writes pass/fail report |
| M9 | Live activation | runtime config switches app into live mode without changing count authority |
| M10 | Periodic audit loop | audit creates disputes/retraining triggers and never mutates Runtime Total |
| M11 | Dashboard states | UI shows onboarding, live, audit, and needs-review states |
| M12 | Regression closeout | backend tests plus Factory2/IMG proof paths remain intact |

## Checkpoint Reviews

Use automated review after machine verifiers pass, not instead of tests.

```text
focused tests / verifier
  -> Codex review
  -> accepted fixes, if any
  -> rerun focused tests
  -> rerun Codex review until no accepted/actionable findings
```

Use Claude or Oracle only for milestone-level architecture risk, not every small
patch. Good escalation points are M1 closeout, M6 calibration semantics, M8 blind
replay gates, and M10 audit mismatch policy.

## Stop Rules

Stop and ask Thomas only when:

- a real RTSP URL or camera credential is required
- cloud teacher permission is required
- the same verifier fails twice for the same root cause
- a change would alter live count authority
- a proof contradicts the architecture
- the choice is product behavior, not implementation detail

## M1 Recorder Contract

The recorder is a sidecar. It records durable chunks for onboarding and audit. It
does not feed frames to `VisionWorker`.

M1 output:

```text
/Users/thomas/FactoryVisionArtifacts/recordings/<station_id>/
  segment_manifest.json
  segments/
    20260608T120000_20260609T015111Z_8f5b0948.mkv
    20260609T015111Z_efa9d71b_000000.mkv
```

RTSP and realtime-file recordings use wall-clock segment names plus a per-run
recording id. Fast local file replay uses the per-run recording id plus a
sequence number. Both modes are restart-safe and avoid same-second overwrite
collisions.

Manifest rows must include:

- station id
- segment id/path
- file size
- SHA-256 hash
- redacted source URI hash, not raw RTSP credentials
- start/end wall timestamps
- duration, codec, dimensions, FPS estimate
- full-stream decode status and probe error when applicable
- privacy mode
- pinned reason for onboarding/audit chunks

Default container is MKV because short RTSP MP4 chunks can be fragile around
keyframe and reconnect boundaries. MP4 remains a CLI option when needed.
