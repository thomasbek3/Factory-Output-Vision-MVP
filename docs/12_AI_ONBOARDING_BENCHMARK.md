# AI Onboarding Benchmark

Updated: 2026-06-04

## Purpose

This benchmark tests the proposed AI-only station onboarding loop on prerecorded footage before it becomes product runtime.

The benchmark answers:

```text
Can the system watch an unseen station video, create blind teacher labels, build consensus, assemble a station dataset, and decide whether it is ready for training or needs more evidence?
```

It does not create validation proof by itself.

## Blind Boundary

Held-out truth is allowed only at the final grading step. It must not be passed into:

- frame sampling
- candidate window creation
- teacher prompts or teacher labels
- consensus building
- dataset assembly
- detector training or detector evaluation

The report records:

```json
{
  "blind_boundary": {
    "held_out_truth_used_by_onboarding": false,
    "held_out_truth_used_only_for_final_grade": true,
    "expected_total_redacted": true
  }
}
```

## Current Harness

Entry point:

```bash
.venv/bin/python scripts/benchmark_ai_onboarding.py \
  --video demo/demo_counter.mp4 \
  --station-id demo-counter-autopilot-v1 \
  --minutes 5 \
  --teacher-provider dry_run_fixture \
  --teacher-count 3 \
  --min-teacher-agreement 2 \
  --output data/reports/onboarding/demo_counter_autopilot_v1_benchmark.json \
  --work-dir data/reports/onboarding/demo_counter_autopilot_v1_work \
  --force
```

Make target:

```bash
make benchmark-onboarding
```

The first provider is `dry_run_fixture`. It proves the artifact flow and refusal behavior without making a network/model call. It should produce `needs_real_teacher_or_more_footage`, not a fake success.

## Artifact Flow

```text
prerecorded video
  -> sampled frames
  -> candidate windows
  -> teacher labels
  -> consensus events
  -> consensus dataset
  -> optional detector eval
  -> held-out grade
  -> benchmark report
```

Output shape:

```text
data/reports/onboarding/<station>_benchmark.json
data/reports/onboarding/<station>_work/
  frames/
  frames_manifest.json
  candidate_windows.json
  teacher_labels.json
  consensus.json
  dataset/
    data.yaml
    dataset_manifest.json
```

## Pass/Fail Meaning

| Status | Meaning |
| --- | --- |
| `needs_real_teacher_or_more_footage` | No usable teacher consensus yet |
| `needs_training_dataset` | Consensus exists but dataset could not be assembled |
| `ready_for_training_or_replay_check` | Consensus dataset exists and can move to train/replay |
| `fail_replay_or_consensus_mismatch` | Held-out grade says the blind result missed tolerance |

## Next Implementation Step

Add a real teacher provider behind the same output contract:

```json
{
  "event_type": "completed_output_placement",
  "countable": true,
  "event_ts": 123.4,
  "box_xyxy": [100, 200, 400, 500],
  "confidence": 0.86,
  "rationale": "worker places finished item in output zone"
}
```

Recommended provider order:

1. local Moondream/Cosmos-style teacher for offline setup
2. OpenAI/frontier VLM teacher only when cloud-assisted setup is explicitly approved
3. second teacher for consensus
4. detector replay gate

## Promotion Rule

This benchmark can create training candidates. It cannot promote product claims.

Promotion still requires the normal validation path:

- trained station detector
- real app replay
- app-vs-truth comparison when truth exists
- no teacher labels as validation truth
- registry update only after clean proof
