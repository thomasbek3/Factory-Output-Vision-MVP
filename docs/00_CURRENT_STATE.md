# Current State

Updated: 2026-06-13

Factory Vision Output Counter MVP: an offline FastAPI + React/Vite appliance that
counts finished output placements from camera or file-backed video, with an
auditable runtime count and no cloud dependency.

> **New here? Read this section first.** There are now **two tracks**, because the
> live factory camera angle broke the original detection approach. Track A is the
> proven runtime for earlier boxable test videos. Track B is the current focus:
> the live overhead wire-frame station, which pivoted from YOLO to action
> recognition. Most active work is Track B.

## Track B — Live overhead station: action-recognition pivot (CURRENT FOCUS)

The live station is a **fixed overhead camera** over a welding/output bench. The
finished product is **thin wire-lattice frames**. From overhead, that product is
effectively **unboxable**, and YOLO object detection failed hard here:

- The day-2 trained detector scored **0/7** on the blind exam and **0% recall on
  its own training images** (`cls_loss` stuck ~4.2; mAP 0).
- Boxing was proven impossible three ways: the output pile is an indistinguishable
  lattice ("a noodle in a bowl of noodles"); the carried frame merges into the
  worker's body even when zoomed; "the newest frame" is not visually separable in
  a still.

The discriminative signal here is the **action over time** (carry → place → leave),
not an object in a single frame — which is exactly why a human (and the Codex
teacher) reads it perfectly while a box detector cannot. So the live station uses
**camera-only action recognition** (the approach Drishti productized for manual
stations):

```text
fixed camera
  -> ZONE TRIPWIRE (cheap pixel change detector on the output zone; no AI)
  -> per-candidate CLIP of the zone (before / during / after)
  -> small VIDEO MODEL judges: placement? yes / no
  -> debounced state machine -> runtime count
```

- The **tripwire** is dumb and high-recall: flag every change, tolerate false
  alarms. The **model** is the precision filter. The **counter** debounces so one
  placement counts once.
- **Codex (LLM) and humans label CLIPS** to train the model. Teacher labels are
  used only at training time; the small model runs live with no teacher in the
  loop. This respects the existing teacher/advisory boundary (below).

### Status (2026-06-13)

- **Tripwire recall PROVEN: 7/7** on the human+Codex-verified exam hour (caught all
  seven known placements within 1–9 s; the day-3 motion miner got only 4/7). The
  foundation — reliably *catching* placements — works.
- Pipeline built on branch `day4-action-recognition`: `app/services/zone_tripwire.py`,
  `clip_dataset.py`, `clip_models.py`, `placement_counter.py`; CLIs
  `run_zone_tripwire.py`, `validate_tripwire_recall.py`, `extract_clip_dataset.py`,
  `label_clips.py`, `train_clip_student.py`, `run_clip_exam.py`. 602 tests green.
- Model contenders wired for a bake-off: `stack3_mobilenet` (baseline),
  `twostream` (+optical flow), `video_x3d` (torchvision `r3d_18`), `video_vmae`
  (VideoMAE) — front-runner is VideoMAE.
- Output-zone polygon CONFIRMED by Thomas (matches where frames are placed). The
  output pile is stable / spray-painted to a fixed spot, which keeps the
  fixed-zone registration valid.
- **NEXT GATE — the MODEL (precision).** Needs human-labeled clips. Thomas labels
  recorded footage (`.../factory_live_day1/label_session/day1_pm_10x.mp4`, a 10x
  scrub of 12:00–15:20) → bake-off trains all contenders → the blind 7-placement
  exam picks the winner and gives a real accuracy number.
- **Governance:** this track is an **evaluation lane** (per ADR 0003) until it
  passes the exam gate. It is NOT yet promoted and NOT a live-camera field claim.
  See `docs/decisions/0004-pivot-from-yolo-to-clip-action-recognition.md` and the
  spec `docs/specs/day4_action_recognition_spec.md`.

## Track A — YOLO event runtime (proven on boxable test cases)

For the earlier test videos the YOLO/event runtime is real, validated, and remains
the **system of record** (ADR 0001). These results stand:

| Case | Status | Truth Total | Result | Primary Comparison |
| --- | --- | ---: | --- | --- |
| Test Case 1 / Factory2 | promoted test case | 23 | 23/23 clean visible app run | `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json` |
| IMG_3262 | verified candidate | 21 | 21/21 clean visible app run | `data/reports/img3262_app_vs_truth.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3_ledger_v2.json` |
| IMG_3254 | verified candidate | 22 clean-cycle | 22/22 clean visible app run | `data/reports/img3254_app_vs_truth.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json` |
| IMG_2628 | verified candidate | 25 | 25/25 clean visible app run | `data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_v1.json` |

The registry lives in `validation/registry.json`; per-case manifests in
`validation/test_cases/`. YOLO works where the product is boxable; the live
overhead wire station is the case it does not, hence Track B.

## Binding Validation Rules (apply to BOTH tracks)

- Real app proof uses `FC_DEMO_COUNT_MODE=live_reader_snapshot`.
- Carried/placed-piece proof uses `FC_COUNTING_MODE=event_based`.
- Promotion proof runs at `FC_DEMO_PLAYBACK_SPEED=1.0`.
- The dashboard Runtime Total must start at `0` and increment from real ordered
  processed frames.
- Captured app events must compare cleanly to reviewed human truth:
  `matched_count == truth total`, `missing_truth_count == 0`,
  `unexpected_observed_count == 0`, `first_divergence == null`.
- For Track B, the analogous gate is the blind 7-placement exam
  (`scripts/run_clip_exam.py`): catch all 7, zero false counts.

## Non-Negotiables

- No deterministic replay as validation proof.
- No timestamp reveal.
- No fake UI updates.
- No offline retrospective count presented as app proof.
- No hardcoded video-specific hacks.
- No threshold loosening solely to force a final total.
- No Reolink/RTSP field claim until the same runtime path is validated on a real
  live camera stream.
- Never train on the 7 held-out exam placements — they are the only verified test
  set for Track B.

## Artifact Storage Boundary

Heavy factory artifacts are local-first. GitHub stores code, docs, validation
registry, manifests, schemas, and small proof summaries. Raw videos, large frame
dumps, model libraries, and embedding/search DBs live outside normal Git.

Local artifact root: `/Users/thomas/FactoryVisionArtifacts` (symlink to the
Crucial X9 archive). Durable policy and the local raw-video index live in
`docs/07_ARTIFACT_STORAGE.md` and `validation/artifact_storage.json`.

## Active Learning / Teacher Boundary

- Live Runtime Total stays AI-only: YOLO/event-based for Track A, the small clip
  model for Track B. No teacher/VLM is in the live counting loop.
- Codex / frontier teachers / Moondream are advisory label-and-audit helpers used
  at training time only. Teacher labels start `bronze` / `pending`; they are not
  validation truth. Gold labels require human/reconciled verification.
- Cloud-assisted labeling/audit requires explicit permission; it must not happen
  silently.
- Promotion of any model/settings must pass the registry cases (Track A) or the
  blind exam (Track B). Static-detector or starved-model failures are recorded as
  learning cases, not forced numeric predictions.
