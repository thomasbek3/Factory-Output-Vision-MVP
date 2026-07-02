# Day-3 Wide-Net Miner + Recall Gate — Implementation Spec

Status: APPROVED for overnight implementation, 2026-06-12.
Authored by Claude (reviewer). Implementation by Codex (coder).
Branch: `day3-wide-net-miner` (cut from current `day2-zone-miner`).
Rollback point: record the HEAD commit of `day2-zone-miner` before first change.

## Why (one paragraph)

Day-2 proved the architecture end-to-end: zone miner → Codex teacher → boxes →
train → blind exam. But the trained model scored 0/7 on the exam AND 0% recall on
its own 12 training images (cls_loss stuck at 4.2 over 80 epochs). Root cause is
NOT the teacher and NOT a code bug — it is **data starvation**. The miner ranked
candidates by peak motion, which favors the welding bench, and handed Codex only
4 real placements for the whole day. Meanwhile a human scrubbing ONE held-out
hour (15:21–16:28) found 7 placements, every one independently confirmed by
`codex exec` at high confidence. Codex is an accurate detector; it was starved of
candidates. This spec re-tunes the miner from precision-first to **recall-first**
(wide net + flash filter so welding doesn't crowd out placements), adds a **free
recall gate** that measures the new miner against 7 ground-truth placements BEFORE
any teacher spend, and runs across day-1 (minus the exam hour) + day-2 to build a
training set large enough to actually converge.

## Ground-truth constants

- Station: `factory-live-day1`, native 2560x1920.
- Output-zone polygon (unchanged, validated day-2):
  `[[0.48, 0.56], [1.0, 0.56], [1.0, 1.0], [0.48, 1.0]]`
- Welding-bench source polygon (informational):
  `[[0.40, 0.13], [0.78, 0.13], [0.78, 0.50], [0.40, 0.50]]`
- Day-1 segments dir:
  `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding/factory_live_day1/recordings/factory-live-day1/segments/`
- Day-2 segments dir (recording until ~17:00 today; finalize after it stops):
  `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding/factory_live_day2/recordings/factory-live-day2/segments/`
- **Exam hour = HELD OUT, never used for training.** Day-1 window
  15:21:50–16:28:33 (the 63 holdout segments, seg starts `20260611T152150` …
  `20260611T162733`). Its 7 verified placements live at
  `validation/exam/exam_gold_positives.json` and the exam ledger at
  `validation/exam/day1_exam_truth_ledger.json`.

## Gold-positives file (already written, do NOT regenerate)

`validation/exam/exam_gold_positives.json`, schema `exam_gold_positives_v1`:
7 events, each `{id, place_wall_clock, segment_file, offset_in_segment_sec,
verification}`. These are the recall-gate truth. They are TEST data — never inject
them into any training dataset.

## Change 1 — Recall-first proposal knobs (`app/services/onboarding_event_proposer.py`)

Goal: surface ~250–400 zone candidates/day (vs 125), biased to miss as few real
placements as possible. Additive, defaults preserve day-2 behavior.

- Lower the effective zone threshold: add `zone_motion_threshold` override plumbed
  from the pipeline CLI (already exists as an arg on `build_event_proposals`).
  Day-3 run uses `0.018` (was 0.04). Do NOT change the default constant.
- The existing ranked-cap + 20s time-dedup stays, but the cap is raised via CLI
  (Change 4), not hardcoded. Dedup window drops to **12s** (was 20s) so two
  genuine placements <20s apart aren't merged — placements ran ~6 min apart in the
  exam but can cluster.
- No change to the dual-score recording (`motion_score` + `motion_score_output_zone`
  already both stored per sample).

## Change 2 — Flash-ratio filter as a first-class gate (`app/services/onboarding_event_proposer.py`)

Welding flash brightens the WHOLE frame, so its zone/full-frame motion ratio ≈ 1.
Real pallet activity is zone-local, ratio ≥ ~2. Use this to drop flash candidates
cheaply, preserving recall on real placements.

- For each event proposal, compute `flash_ratio = peak_motion_score_output_zone /
  max(peak_motion_score_full_frame, epsilon)` and store it on the record.
- New optional arg `min_flash_ratio: float | None = None`. When set, a candidate
  whose `flash_ratio < min_flash_ratio` is dropped from the proposal list and
  counted in a new summary field `dropped_low_flash_ratio`. Day-3 run uses `1.5`.
- Record `flash_ratio` and the `min_flash_ratio` config in the output JSON so the
  recall gate (Change 3) and humans can audit what was filtered.
- IMPORTANT: the filter must run AFTER scoring but BEFORE the ranked cap, so the
  cap fills with real candidates, not flashes.

## Change 3 — Free recall gate (new `scripts/validate_miner_recall.py`)

Runs the proposer over ONLY the exam hour and measures how many of the 7 gold
placements it catches. This is the go/no-go before any teacher spend.

Argparse: `--segment-manifest`, `--gold-positives validation/exam/exam_gold_positives.json`,
`--station-calibration`, `--proposal-mode output_zone_motion`,
`--zone-motion-threshold 0.018`, `--min-flash-ratio 1.5`,
`--match-tolerance-sec 20`, `--out <report.json>`.

- Restrict mining to segments whose wall-clock start is within the exam window
  (derive each gold event's absolute wall-clock from `segment_file` start +
  `offset_in_segment_sec`).
- A gold event is CAUGHT if any surviving candidate's center wall-clock is within
  `match-tolerance-sec` of it.
- Report (print JSON + table): per-gold caught/missed with nearest candidate delta;
  total candidates proposed in the hour; count dropped by flash filter.
- Exit 0 (PASS) when caught ≥ 6 of 7; else exit 1 (FAIL). PASS means the wide-net
  miner's recall is good enough to proceed to a full re-mine. FAIL means motion
  mining alone is insufficient and we escalate to the layer-2 state-change miner
  (out of scope tonight) — report says exactly that.

## Change 4 — Pipeline: raise teacher budget + multi-day input (`scripts/run_factory_day1_pipeline.py`)

- New/used CLI: `--zone-motion-threshold`, `--min-flash-ratio` (thread through to
  the proposer), and raise `--max-teacher-events` to 300 at call time (no default
  change). `--teacher-negative-cap` stays 30.
- `--exclude-window "12:..."`? No — simpler: support `--exclude-segments-after
  <YYYYmmddTHHMMSS>` and `--exclude-segments-before` so the day-1 run can exclude
  the held-out exam hour (exclude segments with start >= `20260611T152150` and <=
  `20260611T162733`). Keep it dead simple: drop any segment whose filename start
  timestamp falls in the excluded [before,after] inclusive range.
- Everything downstream (packets, teacher, local-negative labels, boxes, dataset,
  train, exam) unchanged.

## Run plan (Claude executes after review, not Codex)

1. `validate_miner_recall.py` on the exam hour → must PASS (≥6/7).
2. If PASS: full wide-net re-mine on day-1 **excluding** 15:21:50–16:28:33, teacher
   budget 300. Then (separately, after day-2 recording stops ~17:00) the same on
   day-2 with no exclusion.
3. Merge both days' confirmed positives into one dataset; retrain.
4. Re-run the EXISTING exam gate (same 7-placement ledger, same exam_clip.mp4).
   Compare matched/missing/unexpected vs today's 0/7.

## Tests (extend existing, keep all green)

- `tests/test_onboarding_event_proposer.py`: flash-ratio computed and stored;
  `min_flash_ratio` drops a synthetic global-brightness event (ratio ~1) while
  keeping a zone-local event (ratio ~3); lower threshold yields >= as many
  candidates as higher threshold on the same synthetic input.
- `tests/test_validate_miner_recall.py`: wall-clock derivation from
  segment_file + offset; caught/missed logic at the tolerance boundary; PASS at
  6/7, FAIL at 5/7.
- Pipeline arg test: `--exclude-segments-before/after` removes exactly the
  in-range segments and keeps the rest.
- `.venv/bin/python -m pytest tests/ -q` — all green.

## Non-goals tonight (do NOT build)

- No layer-2 state-change/quiet-snapshot miner (that's the escalation IF the recall
  gate FAILS).
- No new model architecture, no training-hyperparameter changes (data is the fix,
  not lr/epochs — confirm by the recall gate + bigger dataset first).
- No recorder/manifest changes. No dashboard changes.
- Do NOT inject the 7 gold positives into any training set.

## Acceptance checklist

1. `pytest` green.
2. `validate_miner_recall.py` runs and prints an N/7 verdict on the exam hour.
3. Proposer dry-run on the exam-hour segments emits `flash_ratio` per candidate and
   a `dropped_low_flash_ratio` count.
4. Commits on `day3-wide-net-miner` only — surgical, no drive-by edits.
