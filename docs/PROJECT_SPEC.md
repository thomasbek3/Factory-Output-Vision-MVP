# PROJECT_SPEC — Factory Vision Output Counter (v1.0 Camera-Only MVP)
This is the single source of truth for behavior. Do not implement features not defined here.

See ROADMAP.md for v1.5 (beam), v2.0 (OEE/intelligence), and beyond.

Active perception PRD for the current `factory2.MOV` blocker:

```text
docs/PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md
```

Next-phase PRD after the first accepted Factory2 carry:

```text
docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md
```

Work on the worker-entangled carried-panel problem should follow those PRDs before changing count logic.
Current Factory2 human truth target: 23 real carried-panel transfers with 0 false positives.

---

## 1) Mission (non-negotiable)
Build a plug-and-play factory output counter appliance that:
- runs on Ubuntu edge PC
- uses Reolink RTSP camera
- has a local web UI
- requires no CLI after install
- can be configured in under 15 minutes

### 1.1) Current proof target — representative factory footage

For the current wire-mesh/panel proof, success is not generic object counting. The product must prove this physical event rule on representative factory footage such as `factory2.MOV`:

```text
worker brings a new panel from source/process area → system counts 1
worker picks up/repositions an already-output panel → system counts 0
new panel later arrives from source/process area → system counts 1
```

Non-negotiable doctrine:

- detector boxes are observations, not counts;
- output-zone-only motion is not count evidence;
- static finished stacks, resident panels, worker/body overlap, and background edges must not count;
- a count requires a valid source→output delivery token consumed exactly once;
- every count, suppression, and uncertain decision needs reviewable evidence receipts;
- AI/VLM audit reviews receipts and failure cases, but raw VLM counting is not the source of truth.

### 1.2) Definition of done for the current overnight loop

Tonight's loop is done when it produces a repeatable evidence pipeline, not just a raw count:

1. Mine or select candidate event windows from `factory2.MOV`.
2. Generate diagnostic overlays, per-track JSON receipts, image receipt cards, raw crops, and hard-negative manifests.
3. Gate tracks before the count state machine so only approved source-token candidates can count.
4. Export hard negatives with empty YOLO labels and assemble them with reviewed positives into a trainable `active_panel` dataset.
5. Add/verify a detector false-positive evaluation path on hard-negative images before any expensive retraining.
6. Update `.hermes/HANDOFF.md` before and after each bounded cron slice.

A cron slice is successful if it leaves behind one of:

- a tested commit that improves the evidence/training/eval loop;
- a real diagnostic/eval artifact with receipts; or
- a clear failure report explaining exactly which evidence link failed.

It is **not** successful if it merely reports an unaudited raw count.

### 1.3) Morning target — "this works and works well" bar

By morning, the expected outcome is an end-to-end working proof loop on representative footage, not a collection of disconnected utilities. The system should be able to run from factory footage through evidence-backed count/suppress decisions:

```text
factory2.MOV
→ candidate event windows
→ diagnostic receipts/overlays/raw crops
→ perception-gated source-token counting
→ detector/model eval on positives + hard negatives
→ clear accepted_count / suppressed / uncertain report
```

Define "works" as:

- one command or documented command sequence runs the representative `factory2.MOV` proof path without manual intervention;
- the output report separates `accepted_count`, `suppressed`, and `uncertain` events;
- every accepted/suppressed/uncertain event links to receipts: JSON, image card/overlay, and relevant crop/frame evidence;
- raw detector detections cannot directly increment counts;
- output-only, resident/repositioned, static-stack, and worker/body-overlap tracks are suppressed or marked uncertain with explicit reasons.

Define "works well" as:

- on known hard-negative `factory2.MOV` windows, audited false positive counts are zero;
- detector false-positive behavior is measured on exported hard negatives at multiple confidence thresholds, not just one optimistic threshold;
- positive/active-panel behavior is measured separately from hard-negative suppression;
- any newly trained/candidate model must beat or match the current model on hard negatives before it is used in clip eval;
- the final morning report says exactly which clips/windows passed, which failed, and why;
- docs and `.hermes/HANDOFF.md` contain the exact command path to rerun the proof.

The morning bar is **not** met by:

- an unaudited raw count;
- a model metric with no event receipts;
- a pile of generated crops with no count/suppress report;
- suppressing everything without explaining whether the model missed the active panel or the gate rejected it;
- loosening the count state machine to get a nicer-looking number.

If the model still cannot produce a trusted positive count from `factory2.MOV`, the fallback success condition is a precise evidence failure report with receipts showing why: missed active panel, static-stack ambiguity, worker/body overlap, calibration issue, sampling issue, or model false positive. Guessing is failure; auditable abstention is acceptable.

---

## 2) Target environment
- Ubuntu 22.04 LTS (x86_64)
- Python 3.11.8
- CPU-only acceptable

System packages required:
- ffmpeg
- python3-venv

Optional:
- avahi-daemon (for `factorycounter.local`)

### v1.5 additions (not in v1.0 scope):
- USB photo-eye beam sensor pair + Arduino/ESP32 serial bridge
- python3-serial (pyserial)

---

## 3) User flow (v1.0 MVP)
1) Open local UI: `http://<edge-ip>:8080`
2) Enter camera:
   - IP
   - username
   - password
3) Draw output zone (polygon)
4) Optional: enable operator zone (polygon)
5) Click "Calibrate"
6) Click "Start Monitoring"

### v1.5 additions (not in v1.0 scope):
- Step 2.5: Select count source (camera-only or beam+camera)
- If beam: auto-detect USB device, test beam break

---

## 4) Counting strategy (v1.0 MVP)

### v1.0 — Vision-only
Primary method:
- custom active-panel detection + tracking + source-token state machine;
- source/process and finished/output zones are both calibrated;
- detections are treated as observations only — a detection inside output is never by itself a count;
- a count is committed only after a perception-gate-approved source→output delivery token is consumed;
- resident/output-only objects, static finished stacks, repositioning, worker/body overlap, and background edges are suppressed or sent to review;
- every count/suppression/uncertain event produces receipts that can be audited.

Person masking is not always safe with custom in-transit part models because the part may overlap the worker. Use the pre-count perception gate/person-overlap/protrusion logic rather than blindly deleting pixels inside person boxes.

### v1.5 — Beam + vision (not in v1.0 scope)
- USB photo-eye via serial bridge for deterministic count
- Camera provides anomaly context, operator detection, visual timeline
- Vision pipeline runs at reduced FPS (2–5) since it is not counting
- Beam events are the authoritative count source
- Custom YOLO training pipeline for customer-specific parts

### Custom model training (required for real factory parts)
The YOLOv8n COCO pre-trained model detects 80 common object classes but NOT custom factory parts
(wire mesh panels, metal gratings, stamped brackets, etc.). Zero-shot models (YOLO-World, Grounding DINO)
were evaluated and proved unreliable for niche industrial objects.

**Validated workflow (tested 2026-03-18 with wire mesh panels):**
1. Extract 80-120 frames from customer's camera feed (motion-diverse sampling preferred)
2. Upload to Roboflow → auto-label with Grounding DINO + SAM at ~45% confidence
3. Customer reviews/corrects labels in Roboflow annotator (~15-20 min)
4. Export dataset in YOLOv8 format via Roboflow API
5. Fine-tune YOLOv8n locally (50 epochs, ~25 min on CPU, faster on GPU)
6. Deploy custom .pt model file via FC_YOLO_MODEL_PATH env var

**Critical labeling rule:** Label parts IN TRANSIT (being carried/held by worker) — NOT parts
sitting on the output stack. Stacked parts create permanent detections (count = 1 forever).
Transit detections are transient and map correctly to counting events.

**Critical config rule:** Person-ignore pixel masking must be OFF when using a custom model
trained on in-transit parts, because the part is inside the worker's person bbox.
The custom model already excludes person class 0, so pixel masking is unnecessary.

Total onboarding time per customer: ~1 hour from camera footage to counting.
This becomes a product feature: "Upload footage → label parts → train model → count."
The pipeline architecture is model-agnostic — swapping models requires zero code changes.

### Design for v1.5 now
Even in v1.0, the count accumulator should be abstracted behind an interface:
```
count_event(timestamp, source="vision")
```
This makes it trivial to add `source="beam"` in v1.5 without refactoring the metrics/anomaly engine.

---

## 5) Anomaly logic
### Stop
Stop when: zero count for **N minutes**
- default N = 2

### Drop
Drop when: rolling rate < **60% baseline** for **M minutes**
- default threshold = 0.60
- default M = 3

### Operator absent (optional)
Only evaluated when:
- operator zone exists AND
- Drop is active

Operator absent when:
- no person detected in operator zone for **X minutes**
- default X = 2

---

## 6) Must tolerate
- lighting variation
- shadows
- brief occlusion
- camera disconnect and reconnect

### Camera mounting guidance (surface in UI)
Before counting can be accurate, the camera must be properly positioned.
The setup wizard must show guidance:
- Mount camera above and angled down at 30–45°
- Ensure full conveyor width is visible in frame
- Avoid backlighting (don't aim camera toward windows/lights)
- Keep camera on same network as edge PC (wired preferred)

This guidance prevents the majority of accuracy failures. Show as a visual diagram in wizard Step 0.

---

## 7) System states
- NOT_CONFIGURED
- IDLE
- CALIBRATING
- RUNNING_GREEN
- RUNNING_YELLOW_DROP
- RUNNING_YELLOW_RECONNECTING
- RUNNING_RED_STOPPED
- ERROR (rare; only unrecoverable)

State transitions must:
- be logged to DB `events`
- be visible in UI

---

## 8) Storage
SQLite file contains:
- config
- counts_minute
- counts_hour
- events
- health_samples

Retention target:
- keep 90 days (configurable), prune older

### 8.1) Schema design note
`counts_minute` and `counts_hour` rows should include a `count_source` column (default: `vision`).
This adds zero overhead now and makes v1.5 beam integration seamless.
`health_samples` should include `source_kind` (currently `camera` or `demo`, will add `beam` in v1.5).

### 8.2) Logging requirements
The appliance must produce 3 kinds of operational records:

1) `events` table (human-readable event history)
- purpose: operator/support timeline
- must store:
  - state transitions
  - monitoring start/stop
  - calibration started/completed/reset
  - stop detected
  - drop detected
  - operator absent
  - reconnecting
  - reconnected
  - unrecoverable errors
  - user-triggered maintenance actions (restart video, reset calibration, reset setup)

2) `health_samples` table (machine health over time)
- purpose: troubleshooting and support analysis
- sampled periodically during runtime
- must store:
  - timestamp
  - current state
  - last_frame_age_sec
  - reconnect_attempts_total
  - reader_alive
  - vision_loop_alive
  - person_detect_loop_alive
  - source_kind (`camera` or `demo`)
  - rolling_rate_per_min
  - baseline_rate_per_min
  - counts_this_minute
  - counts_this_hour
  - last_error_code (nullable)
  - last_error_message (nullable)

3) rotating text logs on disk
- purpose: low-level support/debug details not suitable for UI tables
- must store:
  - ffmpeg/ffprobe command failures
  - stack traces
  - reconnect backoff details
  - startup/shutdown messages
  - database/schema migration issues
  - model loading issues

Logging rules:
- every Yellow/Red condition must create an `events` row
- every automatic recovery action must create an `events` row
- swallowed exceptions are not allowed; failures must be surfaced as event and/or log entries
- support bundle must include sqlite db + rotating logs + config snapshot + latest frame snapshot

---

## 9) Performance constraints
- Vision processing capped at 10 FPS
- UI snapshot capped at 2 FPS
- Person/body handling must be explicit and testable; do not globally mask custom active-panel detections inside person boxes because carried panels often overlap workers
- Must run for 8 hours without leaking memory

### v1.5 note:
When beam is active, vision processing can drop to 2–5 FPS since counting is handled by beam. This frees significant CPU headroom for future intelligence features.

---

## 10) Deployment constraints
- No Docker
- No YAML editing
- No CLI after install
- Deploy via `.deb` and systemd service
- Service must restart automatically on crash and start at boot

---
