# Day-5 Human-Presence Trigger + Visit Episodes — Implementation Spec

Status: APPROVED, 2026-06-13. Author: Claude (reviewer). Impl: Codex.
Branch: `day5-human-trigger` (from `day4-action-recognition`). Rollback: `c65796a`.

## Why

The day-4 pixel tripwire has perfect recall (14/14 across the exam set and Thomas's
PM set) but massively over-fires: 1,142 raw candidates over 2.6 h that dedup to ~64
real events. Cause: motion + quiet-pile detectors both fire per event, the quiet
path re-probes every 3 s, and tight clusters aren't collapsed. Pixel change also
fires on welding flashes and lighting noise.

A placement REQUIRES a worker at the pallet, and person detection is a solved,
off-the-shelf capability (validated: COCO YOLO boxed the overhead worker in 4/4
test frames). So gate candidates on HUMAN PRESENCE: it is semantic, kills flash/
noise/duplication, and gives a clean event boundary (one visit = one candidate).
Keep the pixel pile-diff as a recall backstop.

## Ground truth (reuse, never train on the exam 7)

- Output-zone polygon (confirmed): `[[0.48,0.56],[1.0,0.56],[1.0,1.0],[0.48,1.0]]`.
- Recall sets: exam 7 (`exam_gold_positives.json`, clip offsets 165/510/781/1104/
  1475/1822/2172) and Thomas's PM 7 (`label_session/day1_pm_human_labels.txt`,
  camera wall-clock 12:39:22, 12:45:55, 12:52:54, 12:59:33, 13:05:18, 14:25:15,
  15:19:19).

## Change 1 — Person-presence trigger (`app/services/zone_tripwire.py` or new `person_trigger.py`)

- Add a `person_presence` trigger mode using an off-the-shelf COCO detector
  (`ultralytics` YOLO, `yolov8m.pt`, class 0 = person). Default model `yolov8m.pt`,
  configurable; fall back to `yolov8n.pt` if `m` weights are unavailable (log it).
- Run person detection on the sampled frames (same fps as the tripwire). A frame
  counts as "occupied" when a person box with `conf >= person_conf` (default 0.35)
  overlaps the **trigger zone** (Change 2). Use box-center-in-zone OR IoU > 0.
- Config additions to `TripwireConfig`: `person_conf=0.35`, `person_model="yolov8m.pt"`,
  `presence_gap_sec=8.0` (Change 3), `episode_max_sec=60.0` (Change 4),
  `trigger_zone_margin=0.15` (Change 2). All validated.
- If `ultralytics` is unavailable, `person_presence` mode skips with a clear error
  (do not break the suite); the pixel modes still work.

## Change 2 — Oversized trigger zone

- The detection/judging zone stays the output polygon. The TRIGGER zone is that
  polygon's bounding box expanded by `trigger_zone_margin` (default 15%) on each
  side (clamped to frame), so a worker reaching in from the edge still trips it.
- Helper `expand_zone(polygon, margin, frame_w, frame_h) -> bbox`. Unit-tested.

## Change 3 — Visit episodes (replaces time-window dedup)

- An EPISODE = a maximal run of occupied frames, allowing gaps up to
  `presence_gap_sec` (default 8 s) so a brief step-out or a one-frame detector
  dropout does not split a visit. Episode start = first occupied frame; end = last
  occupied frame before an unbroken absence > `presence_gap_sec`.
- One episode -> one candidate, `trigger_mode="person_visit"`, center = episode
  midpoint, bracket spans the episode (+/- a small pad, default 2 s).
- This is the dedup: ~1,142 pixel candidates -> ~64 visit candidates expected.

## Change 4 — Visit-length cap (undercount guard)

- If an episode exceeds `episode_max_sec` (default 60 s), split it into consecutive
  sub-clips of <= `episode_max_sec`, each emitted as its own `person_visit`
  candidate. Prevents a long visit containing multiple placements from collapsing
  into one count. Record `episode_split_index`/`episode_split_count` on each.

## Change 5 — Pile-diff backstop merge

- Keep the existing `quiet_state_diff` detector. After building person-visit
  episodes, fold pile-diff candidates in: if a pile-diff center falls inside an
  existing episode window, drop it (already covered); if it falls OUTSIDE all
  episodes, KEEP it as its own `quiet_state_diff` candidate (a placement with no
  detected person — recall insurance). Drop the noisy `motion_burst` mode from the
  default candidate set (superseded by person presence); keep it behind a flag.
- Net default output = person-visit episodes + orphan pile-diff candidates.

## Change 6 — Recall gate update (`scripts/validate_tripwire_recall.py`)

- Run the new person-presence + backstop pipeline; report N/7 on BOTH recall sets.
- PASS requires >= 6/7 on each set. (Day-4 pixel tripwire got 7/7 on both — do not
  regress.) Also print candidate count before/after dedup so the ~64 reduction is
  visible.

## Tests (extend; keep all green)

- Person trigger: monkeypatch the detector to return synthetic boxes; a box in the
  trigger zone marks occupancy; conf below threshold does not; box outside zone
  does not.
- Oversized zone: a box overlapping only the margin (not the core polygon) still
  triggers; `expand_zone` math correct and frame-clamped.
- Episodes: occupied runs with a < gap split merge into one; a gap > `presence_gap_sec`
  splits into two; episode -> single candidate with correct span.
- Visit cap: a 130 s synthetic episode splits into 3 sub-clips.
- Backstop merge: a pile-diff inside an episode is dropped; one outside is kept.
- Recall: synthetic occupancy timeline catches gold timestamps; PASS at 6/7.
- `ultralytics`-missing path skips cleanly.

## Non-goals

- No change to the clip judge / bake-off (Change 5 of day-4). No retraining. No
  live RTSP wiring. No recorder/manifest/dashboard edits. Never train on the exam 7.

## Acceptance

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Recall gate prints >= 6/7 on BOTH sets with the new pipeline, and shows the
   candidate-count dedup (~1,142 -> ~64 on the PM window).
3. `run_zone_tripwire.py` with `--trigger person_presence` produces person-visit
   candidates on a real clip outside the exam window.
4. Commits on `day5-human-trigger` only.
