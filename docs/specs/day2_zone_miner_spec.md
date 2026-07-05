# Day-2 Output-Zone Miner — Implementation Spec

Status: APPROVED for overnight implementation, 2026-06-12.
Authored by Claude (reviewer). Implementation by Codex (coder).
Branch: `day2-zone-miner`. Rollback point: commit `a182691`.

## Why (one paragraph)

Day-1 run proved the teacher (Codex CLI) judges packets correctly but the motion
proposer fed it the wrong moments: 4,385 full-frame motion events dominated by
the welding bench, blind even-stride capped to 70, ~3% time coverage, zero real
placements sampled. Ground truth (human + boundary frames) shows the output
stack grew 13:06–13:47 (lost to recording stall) and massively 13:47–16:27 (on
tape). This spec re-aims mining at the output zone, validates for free against
the known growth windows BEFORE any teacher spend, fixes the packet crops that
silently fall back to full-frame, and cuts teacher-judged negatives from 512 to
a small diverse sample.

## Ground-truth constants (for validation)

- Station: `factory-live-day1`, native frames 2560x1920 (4:3).
- Segments: `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding/factory_live_day1/recordings/factory-live-day1/segments/` (423 x ~60s mkv, names = local wall-clock start `%Y%m%dT%H%M%S_<recording_id>`).
- Known growth windows (local 2026-06-11): `12:26–13:05` (subtle growth) and `13:47–16:27` (heavy growth). `13:05–13:47` lost to stall — zero candidates expected there.
- Placements are sparse fast events, est. 20–60/day, seconds each.

## Output-zone polygon (initial value, pending human sanity-check)

Normalized to frame size, derived from boundary frames; pallet + stack splay,
excluding the wheeled cart at lower-left and the welding table above:

```json
[[0.48, 0.56], [1.0, 0.56], [1.0, 1.0], [0.48, 1.0]]
```

## Change 1 — Station calibration file (REUSE existing module)

`app/services/station_calibration.py` already provides
`build_station_calibration(source_polygons=..., output_polygons=..., ignore_polygons=...)`,
`write_station_calibration`, `read_station_calibration`, `validate_station_calibration`.
Do NOT write a new schema.

- Add a small CLI `scripts/research/factory2/write_station_calibration.py` (argparse: `--station-id`,
  `--output-polygon` as JSON string, `--source-polygon` optional, `--out` path,
  `--force`) that calls the existing builder/writer.
- Produce the day-1 file at
  `/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding/factory_live_day1/station_calibration.json`
  with the polygon above as the single entry in `output_polygons` and the welding
  table region `[[0.40, 0.13], [0.78, 0.13], [0.78, 0.50], [0.40, 0.50]]` as a
  `source_polygons` entry (informational).

## Change 2 — Zone-gated motion scoring (`app/services/onboarding_event_proposer.py`)

New keyword args on `build_event_proposals` (all optional, defaults preserve
current behavior; existing tests must pass unchanged):

- `output_zone_polygon: list[list[float]] | None = None` (normalized points)
- `proposal_mode: str = "full_frame_motion"` — accept `"output_zone_motion"`.
- `zone_motion_threshold: float = 0.04` — fraction of ZONE pixels changed
  (zone is much smaller than frame; threshold is relative to zone area, NOT
  frame area — this is the calibration-critical detail).

Implementation:

- In `sample_segment_motion` (or a wrapper), when a polygon is provided, build a
  uint8 mask once per segment at the sampled frame size via
  `cv2.fillPoly` (denormalize points by width/height). Every sample then records
  BOTH `motion_score` (existing full-frame metric, unchanged) and
  `motion_score_output_zone` (same diff metric computed over masked pixels,
  normalized by zone pixel count).
- In `"output_zone_motion"` mode, clustering/threshold/peak-selection uses
  `motion_score_output_zone` with `zone_motion_threshold`. `candidate_reasons`
  gains `"output_zone_motion_above_threshold"`. Keep full-frame score in the
  proposal record for diagnostics.
- Each event proposal record additionally carries
  `peak_motion_score_output_zone` so the cap policy can rank without re-reading
  samples.
- `config` block in the output JSON gains `proposal_mode`,
  `zone_motion_threshold`, and `output_zone_polygon` (null when absent).
- Schema: bump `GENERATED_BY` to `motion_event_proposer_v2`; `SCHEMA_VERSION`
  unchanged (fields are additive).

## Change 3 — Ranked cap replaces even-stride (`scripts/research/factory2/run_factory_day1_pipeline.py`)

- New CLI args: `--station-calibration <path>` (reads polygon via
  `read_station_calibration`, first entry of `output_polygons`) and
  `--proposal-mode {full_frame_motion,output_zone_motion}` (default
  `full_frame_motion` for back-compat).
- In `output_zone_motion` mode, replace the even-stride sampling in the
  `day1_event_cap` step with: sort event candidates by
  `peak_motion_score_output_zone` desc; greedily keep while skipping any
  candidate whose center wall-clock time is within 20s of an already-kept one;
  stop at `--max-teacher-events`. Record
  `"sampling": "top_n_zone_score_time_dedup"` in the summary. Even-stride path
  stays for full-frame mode.

## Change 4 — Real zone crops (`app/services/teacher_evidence_packets.py`)

Current behavior is marked `full_frame_fallback_until_station_roi_packet_exists`
— the `output_zone_crop_sequence` assets are NOT real crops. Fix:

- When a calibration polygon is available (thread it through from the pipeline),
  render `output_zone_crop_sequence` and `stack_crop_sequence` as actual crops
  of the polygon's bounding box +10% margin, from the NATIVE-resolution frames
  (no downscale below 768px crop width). Keep `before_full`/`during_full`/
  `after_full` full-frame images for teacher context.
- Replace the fallback marker with `"crop_source": "station_calibration_output_zone"`
  vs `"crop_source": "full_frame_fallback"` so packets self-describe.

## Change 5 — Teacher negative budget (`scripts/research/factory2/run_factory_day1_pipeline.py` + packet builder)

- New CLI arg `--teacher-negative-cap` (default 30). Stable negatives are
  diversity-sampled by time-of-day (even stride across the day — stride is fine
  HERE because negatives should be representative, not peak-ranked). Sampled
  negatives go to the teacher as today. The remainder are NOT packetized for
  the teacher; they are written to the labels file directly with
  `verification_decision: "refute_completed"`,
  `teacher_output_status: "local_negative_not_teacher_judged"`,
  `label_authority_tier: "bronze"`, `training_eligible` per existing fusion
  rules for negatives.

## Change 6 — Free validation harness (new `scripts/research/factory2/validate_zone_mining.py`)

Argparse: `--proposals <event_proposals.json>`, `--growth-windows` (JSON, default
`[["12:26","13:05"],["13:47","16:27"]]`), `--stall-windows` (default
`[["13:05","13:47"]]`), `--date 2026-06-11`, `--top-n 70`.

- Convert each event candidate to wall-clock: segment filename start time +
  `center_offset_sec`.
- Report (print JSON + human table): candidates per 15-min bucket; of the top-N
  by zone score: count inside growth windows, count in stall windows (must be
  0 — stall has no footage; >0 means a timestamp bug), count outside both;
  top-20 list with wall-clock + zone score.
- Exit 0 with `"verdict": "PASS"` when >=60% of top-N fall inside growth
  windows AND >=10 candidates land in 13:47–16:27; else exit 1 with
  `"verdict": "FAIL"`. This gate runs BEFORE any teacher spend.

## Tests (extend existing files, keep all green)

- `tests/test_onboarding_event_proposer.py`: synthetic-frame test — motion
  inside polygon scores high in zone metric while motion outside polygon scores
  ~0 in zone metric but high in full-frame metric; mode default unchanged.
- New `tests/test_validate_zone_mining.py`: wall-clock conversion, PASS/FAIL
  verdict logic, stall-window-must-be-empty check.
- Cap policy test: top-N + 20s dedup picks the right subset from a synthetic
  proposal list.
- Crop test in `tests/test_teacher_evidence_packets.py`: polygon provided →
  crop dims match bbox+margin and `crop_source` field set.
- Run: `.venv/bin/python -m pytest tests/ -q` — everything green.

## Non-goals tonight (do NOT build)

- No quiet-snapshot/bisection miner (next iteration, after this validates).
- No teacher invocation, no training run, no touching recorder/manifest code.
- No dashboard changes.

## Acceptance checklist

1. `pytest` green.
2. `scripts/research/factory2/write_station_calibration.py` produced the day-1 calibration file.
3. Proposer dry-run on 3 real segments (e.g. the 14:0x chunks) emits zone scores.
4. Commit(s) on `day2-zone-miner` only — surgical, no drive-by edits to
   unrelated files.
