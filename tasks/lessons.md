# Lessons Learned

## 2026-05-04: real_factory Review-To-Training Boundary

1. **Reviewed event timestamps are not positive detector boxes.** A filled `real_factory` worksheet can create a gold event ledger and reviewed positive/negative anchors, but a YOLO export still needs explicit positive bounding-box labels before detector training is ready.
2. **Pending worksheets should still produce poison-checkable manifests.** A pending active-learning dataset manifest with all rows in the `review` split lets the registry track the next step without accidentally making bronze labels training-eligible.
3. **Review converters must fail closed by default.** The safe default is to refuse truth outputs while any worksheet row is blank or unclear; `--allow-pending` is only for bronze status artifacts.

## 2026-05-03: Static-Detector Abstention

1. **A static detector firing on every sampled frame is not a weak count signal; it is an abstention signal.** If active transfer detectors are dead and the only high-recall model is a known static/resident-material detector, do not publish its runtime total as a valid blind estimate.
2. **Failed diagnostics are still learning data.** The false runtime events become hard-negative review candidates, while the reviewed real placements become gold positives for a video-specific detector.
3. **Detector transfer must gate runtime interpretation.** Parameter-sensitive dead-track counts from static detectors should route to `numeric_prediction_allowed=false` and the learning registry before anyone treats the number as product evidence.

## 2026-05-01: Factory2 Real-Time Bar

1. **“Near real-time” is not the target.** For Factory2 demo work, the bar is sustained true `1.0x` real-time behavior on the actual app path, not “close enough” wall-clock speed.
2. **Do not redefine the success metric during planning.** If the user says real time, keep the task framed as real time in `tasks/todo.md`, implementation notes, and verification.
3. **Correctness still constrains speed.** Real-time only counts if it preserves real processed-frame semantics, placement-timed increments, and the final `23/23` truth match.
4. **Synchronous demo pacing must follow the source clock.** A fixed post-frame sleep carries lag forever after expensive frames. For one-pass file-backed live demos, pace against each processed frame's source timestamp and skip sleep only when the worker is behind that clock.
5. **Non-divisor FPS values need fractional sampling.** Rounded integer strides make settings like `9.5 FPS` lie about the requested cadence. Sampling by source timestamps keeps frame selection honest, even if a specific FPS still fails the truth diff.
6. **The dev dashboard should proxy API calls through Vite.** Direct cross-origin fetches can execute backend actions while the browser reports `Failed to fetch`, leaving diagnostics stale. Same-origin proxying keeps the visible UI honest.
7. **A new video is a new proof problem.** Do not assume Factory2 calibration, truth count, or event timing transfers to `real_factory.MOV`, `IMG_2628.MOV`, or `IMG_3262.MOV`. Build or load a human truth ledger, run the actual app path, then compare.
8. **Reolink remains an unvalidated claim.** The architecture should transfer to RTSP, but a real camera can introduce codec, network, exposure, reconnect, and angle problems. Do not say Reolink works until a real stream is validated.

## 2026-04-28: Factory2 Definition Of Done

1. **Proof-only success is not done.** If Factory2 counts in `scripts/run_factory2_morning_proof.py` but the actual worker/app runtime path still shows `counts_this_hour: 0`, the task is still in progress.
2. **Do not stop at diagnostics or receipts.** Diagnostics exist to unlock counting, not to replace it.
3. **For Factory2, verify the real product path.** Run the actual `VisionWorker`/FastAPI monitoring flow on `factory2.MOV`, not just unit tests or proof scripts.
4. **If stuck on the next move, escalate to Oracle before asking the user for direction.**
5. **Default to continuing, not summarizing.** If the next step is already implied by the PRD, latest failure, or verification result, keep going instead of pausing to ask what to do next. Stop only for a real blocker, a risky decision, required approval, or actual completion.

## 2026-04-28: Factory2 Recall Recovery

1. **One accepted carry is only the midpoint.** After proof/runtime count one real carry, the target becomes the human truth set: `23` counts on `factory2.MOV` with `0` false positives.
2. **Broad mixed windows hide recall.** When long busy periods undercount, split them into narrow event-centered windows before touching thresholds.
3. **Do not merge mutable diagnostics.** Freeze or copy finalized diagnostic directories before building one merged proof artifact, or the report can be contaminated by in-progress sidecar regeneration.
4. **Blocked worker-overlap cases need crop-level training evidence.** If recall stalls, export the blocked receipt crops and label panel-vs-worker separation cases instead of inventing looser count logic.
5. **Merged accepted receipts can still double-count.** When overlapping windows both approve the same physical carry, dedupe by overlapping accepted receipt intervals and keep only one canonical receipt in the top-level accepted total.
6. **Do not silently train on placeholder labels.** The crop-training builder must report `ready_for_training: false` until the review package actually contains `worker_only` and `static_stack` truth labels.
7. **Split crop datasets by physical track, not by crop file.** All crops from the same `diagnostic_id + track_id` need to stay in one split to avoid train/val leakage from near-identical receipt frames.

## 2026-03-18: Vision Pipeline Architecture Overhaul

### Key Decisions Made

1. **Blob detection is dead.** Background subtraction + contour detection was the original MVP approach. It fails catastrophically in real factories: counts shadows, hands, reflections, lighting changes. Never go back to this.

2. **YOLO is the only viable path.** YOLOv8n provides real object detection with bounding boxes, class labels, and confidence scores. It knows what a person is (class 0) and can be trained to detect custom parts.

3. **COCO pretrained model can't detect custom factory parts.** YOLOv8n ships with 80 COCO classes (person, car, bottle, etc.). Wire mesh panels, stamped brackets, custom parts = not in COCO. Zero-shot models (YOLO-World, Grounding DINO) were also unreliable for niche industrial objects.

4. **Custom YOLO fine-tuning per customer is the real product.** Extract ~100 frames from customer video → label on Roboflow → fine-tune YOLOv8n → deploy custom model. Total time: ~1 hour. This is the moat.

### Failed Approaches (Red-Teamed and Rejected)

1. **Worker zone-transition counting** — Track worker centroid between "machine zone" and "stack zone." Failed red team: walk-throughs, adjustments, maintenance, multiple stacks all cause false counts.

2. **Single machine-zone return counting** — Count worker returns to machine zone. Failed: worker stays at machine for small parts, zone boundary jitter, lunch returns, shift changes.

3. **Frame differencing in output zone** — Detect pixel changes when parts are placed. Failed: worker's body dominates frame diff (40% vs 2% for part), person masking creates reveal artifacts, wire mesh on wire mesh is nearly invisible to pixels.

4. **Auto-calibration from first N cycles** — Learn debounce from observed cycle times. Failed: if cycles are 3-4 min, takes 30-40 min to calibrate. Cycle times change with parts, workers, time of day. Just use a user-set debounce slider.

### Architecture Decisions

1. **Person-ignore masking must be OFF when using custom model.** Custom model trained on "panel in worker's hands" means the panel is INSIDE the person bbox. Person masking blacks it out. Custom model already excludes person class, so pixel masking is unnecessary.

2. **Label panels in transit, not on the stack.** If you label stacked panels, YOLO detects the stack as 1 permanent object = count stuck at 1. Label only panels being carried/held = transient detections that map to counting events.

3. **Debounce should be user-controlled, not auto-learned.** Simple slider: "What's the fastest you'd produce a part?" Default 3 seconds. User knows their process better than any algorithm.

4. **+/- correction buttons are a feature, not a crutch.** "AI-assisted counting with operator oversight." Safety net for demos and edge cases.

### Roboflow Workflow

- Roboflow auto-label with Grounding DINO works for wire mesh panels at ~45% confidence with prompt "metal flat rectangular metal grid"
- Higher confidence = misses panels, lower confidence = labels random factory equipment
- SAM 3 (Masks) model was used for auto-labeling
- Manual review still needed — some frames auto-label picks up wrong things
- Export as YOLOv8 format → train locally with ultralytics library
- Roboflow API key stored separately (not in repo)

### Training Details

**v1 model (stack detection — FAILED for counting):**
- Dataset: 102 images (71 train, 21 valid, 10 test) from factory2.MOV
- Model: YOLOv8n fine-tuned, 1 class ("panel"), 20 epochs
- Results: 98% precision, 91% recall, mAP50 94.6%
- Problem: Detects STACKS as permanent objects. Detection count is static at 8-9 regardless of worker activity. Useless for counting production cycles.
- Stored at: models/wire_mesh_panel.pt (DO NOT USE for counting)

**v2 model (panel-in-transit — IN PROGRESS):**
- Dataset: 100 frames from factory2.MOV, motion-filtered (80 high-motion, 20 idle negatives)
- Class: "panel" but ONLY labeled when worker is actively carrying/holding a panel
- Key insight: transient detections (appear when carrying, disappear when placed) map perfectly to counting logic
- Roboflow project: panel-in-transit

### Critical Failure: Stack Detection Does NOT Enable Counting

Tested extensively on factory2.MOV. Stack-detection model finds 8-9 panels at the same coordinates every frame. The detection count does NOT fluctuate when the worker moves panels. Approaches tested and failed:
- Machine output zone monitoring (panel present/absent): 1 count vs 7 real (ROI wrong, detections are static stacks)
- Detection count fluctuation: 0 cycles detected vs 6 real (count stays 8-9 constantly)
- Debounce tuning (1.5s to 3.0s): doesn't help when the underlying signal doesn't exist

**The ONLY approach that works: detect the panel IN TRANSIT (being carried). Each transient detection = 1 count.**

### Demo Strategy (~2 weeks out)

- For the demo: use panel-in-transit custom model on the actual factory video
- +/- correction buttons on dashboard as safety net for any detection misses
- Deploy first, improve later — inspired by RMFG/Roboflow factory tour case study (shipped with 60 images in 1 week)
- Don't wait for perfect model. Good enough + correction buttons = shippable product
- Camera should be mounted overhead or at high angle to minimize worker occlusion of carried panel

### Continuous Improvement Loop (Planned)

- Use Roboflow API to auto-collect more training images during production
- Retrain periodically to improve accuracy over time
- More data = better model, and the production camera generates unlimited training data
- This turns every deployment into a data flywheel

### Key Insight: Frame Differencing is Fundamentally Broken for This Use Case

Frame differencing approaches are fragile because the worker's body dominates the visual signal (~40% of pixels change vs ~2% for the part being placed). Person masking creates reveal artifacts. Wire mesh on wire mesh stack is nearly invisible at the pixel level. Direct object detection via custom YOLO is the only reliable approach for arbitrary factory parts. Do not revisit pixel-based approaches.

## 2026-03-19: Event-Based Counting & Model Performance

### Counting Mode Architecture

1. **Two counting modes now exist.** `track_based` (default, ROI + centroid tracking) and `event_based` (detection clustering for transit events). Set via `FC_COUNTING_MODE`.
2. **For non-conveyor factories (worker at station), event-based counting is more robust.** Detecting panels in transit is better than monitoring output stacks because stacks are static and don't produce countable events.
3. **Event-based mode auto-disables person-ignore masking and makes ROI optional.** The transit model already ignores persons, and detections happen across the full frame as the worker moves.

## 2026-04-28: Factory2 Crop-Classifier Promotion Lessons

1. **Blocked worker-overlap crops were not a real negative set.** Manual review of the `worker_body_overlap` receipt package showed the blocked tracks were still mostly real carried panels. Treating them as negatives would have poisoned the second-stage model. Build `worker_only` references from nearby non-track person crops instead.
2. **Single-pass runtime verification cannot use looped demo totals.** In demo mode, [`app/services/frame_reader.py`](/Users/thomas/Projects/Factory-Output-Vision-MVP/app/services/frame_reader.py) runs `ffmpeg -stream_loop -1`, so `counts_this_hour` will eventually overcount on repeated passes. Use a no-loop harness or an explicit loop boundary before claiming a true one-pass `factory2.MOV` result.
3. **Crop-classifier evidence must survive predecessor-chain merges.** Runtime split-track delivery chains merge `_LiveSeparationSummary` state. If crop-classifier fields are not merged there, proof/runtime diverge and split worker-overlap deliveries stay invisible even after the classifier is trained.
4. **Current runtime truth is still below the human target.** After crop-classifier promotion, the refreshed frozen proof reached `accepted_count: 15`, and the no-loop runtime harness reached `final_count: 17` on `factory2.MOV`. The next blocker is source→output chain recall, not person/panel perception alone.

## 2026-04-28: Factory2 Proof Alignment Lessons

1. **Proof recall can move materially just by selecting the right diagnostic set.** An optimizer over the current narrow proof winners plus nearby gap-region windows pushed the best existing-window proof set to `19/23` runtime-event coverage before any new detector/model work.
2. **Two specific runtime-only gaps were recoverable by tighter windows.** `factory2-review-0019-000-010s-panel-v1-8fps` recovered the `5.5s` opener, and `factory2-review-0016-274-294s-panel-v1-5fps` recovered `286.408s`, moving the proof artifact to `accepted_count: 21`.
3. **The final two proof misses are not plain panel-vs-worker misses.** `305.708s` and `425.012s` collapse into an earlier accepted carry plus a later `output_only_no_source_token` stub. Tighter windows that started later lost source evidence entirely; tighter windows that started earlier only restated the earlier accepted carry.
4. **Do not recover proof gaps by reusing prior accepted count authority.** In this dataset, a heuristic that lets an `output_only_no_source_token` stub inherit from a nearby already-accepted carry would likely recover the final two counts, but that reuses prior source authority and is too close to cheating the proof bar.

## 2026-04-29: Factory2 Final-Two Packetization Lessons

1. **Accepted-proof dedupe needs source lineage, not just time overlap.** Overlap-based clustering is not enough once split deliveries and restated receipts exist. Attach a `source_token_key` derived from the source-supporting receipt lineage and treat shared lineage as duplicate proof authority unless new source evidence appears.
2. **Runtime/proof disagreement should be packetized around the runtime event, not argued abstractly.** A runtime-event-centered receipt packet made the final two misses legible: each one reduced to an earlier accepted proof carry plus a later output-only/static-edge stub in the same covering diagnostic.
3. **Do not trust top-level `failure_link` alone when looking for proof stubs.** Some rows with `reason: static_stack_edge` still summarize to `failure_link: worker_body_overlap` because person-overlap flags dominate. Audit tooling for proof/runtime gaps must inspect raw reason as well.
4. **Oracle’s warning held up against the real artifact.** For `305.708s` and `425.012s`, the committed `21`-count proof baseline now packetizes to `shared_source_lineage_no_distinct_proof_receipt`. That is evidence for an honest proof/runtime divergence, not permission to stitch by threshold relaxation.

## 2026-04-29: Factory2 Focused Gap Search Lessons

1. **A new diagnostic-local key is not fresh proof lineage.** Search windows naturally mint new diagnostic-specific `source_token_key` strings. To qualify as fresh proof, the accepted receipt must also be event-local; otherwise it can still be the same earlier physical carry in a new namespace.
2. **Event-locality is the right check for final-gap rescue windows.** In the focused searches, accepted proof receipts often ended `1.5–2.0s` before the runtime event while a later static/output-only stub landed near the runtime timestamp. Those must score as `shared_source_lineage_no_distinct_proof_receipt`, not as recovered proof.
3. **Both 8fps and 10fps sweeps converged on the same answer.** For both divergent events (`305.708s`, `425.012s`), all `12/12` focused windows at `8fps` and all `12/12` focused windows at `10fps` collapsed into earlier accepted lineage plus later stub. That makes the current divergence materially stronger than a single-window anecdote.
4. **Once focused sweeps stabilize, stop spending time on more threshold/fps/window nudges.** After two bounded confirmation bands returned the same `24/24` outcome, the next real lever is a new receipt-construction method or new training/data/model work, not more minor search-parameter churn.

## 2026-04-29: Factory2 Runtime Lineage Lessons

1. **`source_track_id` is not enough.** For runtime/proof alignment, you need explicit lineage provenance, not just the track id or chain id. The decisive field is whether the runtime count consumed a live source token or minted a synthetic fallback token at output.
2. **Both final runtime-only events are synthetic fallback counts.** The from-start runtime-lineage audit showed `305.708s` and `425.012s` as `synthetic_approved_chain_token`, so neither is honest proof authority. Runtime remains `23`; honest proof remains `21`.
3. **Local replays can lie by resetting state.** Short replay windows around `305.708s` restated the earlier `303.508s` count and missed the true runtime-only event. Source-token TTL, resident dedupe, and committed delivery-chain state make these events inherently from-start problems.
4. **Do not promote runtime-only delivery chains into proof by default.** A runtime-backed receipt must reject `synthetic_approved_chain_token` and treat it as `incomplete_source_to_output_path` until a genuinely fresh source-backed lineage exists.
5. **Oracle’s recommendation was correct.** The right escalation path was from-start runtime provenance, not more proof-window searching. Once provenance still showed synthetic fallback, the honest action was to preserve the explicit `runtime 23 / proof 21` divergence.

## 2026-04-29: Factory2 Count-Authority Hardening Lessons

1. **Only two synthetic runtime counts remain unmatched by overlapping proof receipts.** The authority ledger now says: runtime total `23`, proof total `21`, inherited live source token `11`, synthetic with overlapping proof `10`, synthetic without distinct proof `2` (`305.708s`, `425.012s`).
2. **Corrected lineage-window search is exhausted for the final two.** After switching from arbitrary lead/tail guesses to source-history-driven search windows, the focused `5/8/10fps` runs for both remaining events still scored `shared_source_lineage_no_distinct_proof_receipt`.
3. **Synthetic approved-chain events must not mint fake source evidence.** If a runtime count is `synthetic_approved_chain_token`, do not fabricate `source_token_id` or `source_bbox` from the output-side box. Mark it as `count_authority = runtime_inferred_only`.
4. **Do not throw away useful runtime recall just because proof is lower.** Removing synthetic approved-chain count authority from the operational runtime total would likely throw away legitimate recall that already overlaps accepted proof in `10` cases. The safer product move is to separate operational/runtime counts from proof-backed counts.

## 2026-04-29: Factory2 Product-Surface Count Split Lessons

1. **The API cannot blur runtime and proof once authority diverges.** When runtime reaches `23` but proof stays at `21`, the app/backend status must expose separate numbers rather than implying one undifferentiated truth total.
2. **Manual adjustments are neither proof-backed nor runtime-inferred lineage.** Positive operator corrections should still move `counts_this_hour`, but they must not silently inflate `proof_backed_total` or `runtime_inferred_only`.
3. **Synthetic approved-chain counts need to survive serialization.** The event ledger must allow `source_token_id = null`, `reason = approved_delivery_chain`, and `count_authority = runtime_inferred_only` so downstream audit tools see the real provenance.
4. **Schema-backed health snapshots must evolve with the status contract.** Once status gained `runtime_total`, `proof_backed_total`, and `runtime_inferred_only`, the `health_samples` table needed the same columns plus an explicit migration path for older DBs.

## 2026-04-29: Factory2 Final-Two Convergence Lessons

1. **The missing unit was the chain neighborhood, not another proof window.** For the final two unresolved events, the useful evidence is the whole runtime lineage neighborhood: source anchor, nearby source-only context, prior counted delivery, divergent output-only fragment, and trailing output context.
2. **Runtime-only events can hide extra source context outside the old proof receipts.** The divergent chain review package surfaced previously hidden source-only tracks (`104/105/106` and `143/144/145/147/148/149/150`) that were invisible in the simpler prior-accepted-vs-stub packet view.
3. **Total-count agreement is not enough.** Even when runtime hits the human total of `23`, the final two still need per-event review because they could be either true missed proof cases or lucky runtime duplicates.
4. **Static-resident references matter for the final-two rescue dataset.** The divergent-chain labels alone left the relation set incomplete. Pulling proof-side `static_stack_edge` receipts into a dedicated static-resident reference exporter was enough to make the rescue dataset class-complete and `ready_for_training`.
5. **Draft relation labels are not the same as settled truth.** A conservative first pass over the final-two review package produced `21 same_delivery_as_prior`, `5 distinct_new_delivery`, and `11 unclear`. Those draft labels are enough to build the first rescue dataset, but they are still review seed truth, not a proven final answer.
6. **Do not assume a relation problem is learnable from isolated crops.** `same_delivery_as_prior` is a lineage label, not obviously a pure visual category. Before training a model, validate whether the supervision target is single-crop, pairwise, or sequence-level.
7. **A mediocre crop-classifier baseline can be useful as a falsification test.** On the fully draft-labeled local rescue dataset, a quick YOLO11n-cls baseline only reached `top1 = 0.625` on the `test` split, and the `val` split still lacked one class entirely. That is good enough to reject “single-crop classifier solves this tonight,” not good enough to trust for runtime/proof promotion.
8. **Chain-level adjudication is the right first authority layer for the final two.** Once the divergent runtime tracks themselves are relation-labeled `same_delivery_as_prior`, the honest first output is a duplicate-suppression report, not a proof mint attempt. Preserve source-token authority and let the adjudicator say `do_not_mint`.

## 2026-04-29: Factory2 Deterministic Demo Runner Lessons

> Superseded for investor evidence as of 2026-05-01. Deterministic replay was an intermediate debugging/demo bridge. The accepted proof point is now the `live_reader_snapshot` app path that processes ordered frames at `1.0x` and matches truth `23/23`.

1. **The live ffmpeg snapshot loop is the wrong place to derive investor-demo counts.** Even after single-pass EOF handling was fixed, the app-side `reader.snapshot()` counting path still dropped most events on `factory2.MOV` at accelerated playback.
2. **For demo mode, preview and counting need to be decoupled.** The honest fix is a deterministic file-backed runner that replays audited runtime receipts against wall-clock playback while the ffmpeg reader is used only for preview frames.
3. **Restart the demo at monitor start.** If the preview is already mid-file when monitoring begins, receipt reveal and visible playback diverge. Restarting the demo source when `monitor/start` arms the deterministic runner keeps the visible run aligned from frame 0.
4. **The app can now do the thing the offline audit proved.** With `FC_DEMO_COUNT_MODE=deterministic_file_runner` plus the audited `factory2_runtime_event_audit.onepass_2026-04-29.json`, the actual FastAPI app path runs `factory2.MOV` once, reaches `runtime_total: 23`, and transitions to `DEMO_COMPLETE`.
5. **The replayed authority split is only as good as the receipt source.** Replaying the raw one-pass runtime audit surfaces the raw event-authority mix from that audit (`11 source_token_authorized`, `12 runtime_inferred_only`). If the investor/demo story needs a stronger `21/2` authority presentation, the next move is an authority-normalized replay source, not a fake UI total.

### Model Performance & Recall Requirements

4. **53% recall is insufficient for real-time event counting.** Sparse detections don't form reliable temporal clusters. Need 80%+ recall, which requires 150+ labeled training images (currently at 47).
5. **Offline scanning (seeking through video) works even with low recall.** When you can scan every frame, even 53% recall catches most events. Real-time streaming at 10 FPS with sparse detections misses clusters entirely. Real-time needs higher recall.
6. **Wire mesh panel model (v1): 98% precision, 91% recall, mAP50 94.6% with 71 images.** Great detection, but useless for counting — detects static stacks.
7. **Panel in transit model (v2): 94% precision, 53% recall with 47 images.** Promising but needs 3x more training data.

## 2026-04-30: Factory2 Live App Truth Validation

1. **Partial truth diffs need coverage metadata.** A partial app capture without source-video coverage will fake a “missing event” at the first uncovered truth timestamp. Capture and compare reports need `reader_last_source_timestamp_sec` / `observed_coverage_end_sec` so incomplete runs are marked as `incomplete_coverage`, not false misses.
2. **The verified Factory2 app path is real sequential counting, not replay.** A one-pass `live_reader_snapshot` app run on `factory2.MOV` with `event_based` counting and `factory2_ai_only_v1.json` matched the human truth ledger `23/23` with `0` missing and `0` unexpected events.
3. **Launch mode matters as much as code.** A clean app instance launched in `track_based` mode will look broken even if the verified `event_based` path is correct. The investor/demo launch needs a fixed command or wrapper script, not memory.
4. **The investor demo recipe is now explicit.** Use `scripts/start_factory2_demo_app.py` so the app always starts with `FC_DEMO_LOOP=0`, `FC_COUNTING_MODE=event_based`, `FC_RUNTIME_CALIBRATION_PATH=data/calibration/factory2_ai_only_v1.json`, and `10 FPS` processing/reader settings.

## 2026-04-30: Factory2 Live Demo Speed Lessons

1. **The single biggest demo-reader bug was random seeking every sampled frame.** In synchronous single-pass demo mode, calling `capture.set(CAP_PROP_POS_FRAMES, frame_index)` on every processed frame destroyed throughput. Advancing sequentially through sampled indices and reusing the primed first frame removed that seek tax.
2. **Live person/panel analysis should only run in the worker-overlap danger zone.** The expensive silhouette/crop path is only needed when track overlap actually enters the gate's reject corridor. Running it on clear non-overlap tracks wastes time without improving decisions.
3. **Adjacent-frame reuse is safe when the track/person geometry barely changes.** Reusing live separation/crop results across nearby same-zone frames preserved the `23/23` truth match while cutting hot-burst per-frame cost materially.
4. **Runtime person detection should respect its own FPS setting.** Re-running the separate person detector on every processed frame was unnecessary. Caching the last person boxes inside the configured detect interval reduced live-path cost without changing the verified outcome.
5. **A speed change is not real until the app-truth diff still says `23/23`.** The optimized `8094` app run still matched the human ledger exactly, so this slice is a real live-app speedup, not just a microbench win.

## 2026-05-01: IMG_3262 Real-App Validation Lessons

1. **Do not trust `FC_DEMO_PLAYBACK_SPEED=1.0` without measuring wall/source time.** IMG_3262 initially looked configured correctly while source timestamps advanced too fast. A valid real-time claim needs a recorded wall/source ratio from the real app run.
2. **Synchronous demo pacing belongs at the frame-pump boundary.** Worker-level pacing can be bypassed by pending-frame draining or double-subtracted by loop sleep accounting. Pacing `pump_next_demo_frame()` against source timestamps keeps preview, counting, and diagnostics on the same clock.
3. **EOF flush is required for final-second placements.** If a carried/placed object is still an active event track when a one-pass demo reaches EOF, the runtime must flush that active track once with source timestamp authority; otherwise the last legitimate placement is silently missed.
4. **A rough timestamp ledger can create false timing failures.** The IMG_3262 v1 ledger had a `629s` rough marker after the worker had already moved on. Keep the app comparison honest by preserving the failed rough-ledger comparison and creating a reviewed v2 ledger rather than loosening runtime thresholds.

## 2026-05-01: IMG_3254 Candidate Lessons

1. **A detector that improves selected-frame precision can still worsen runtime counting.** IMG_3254 v5/v6/v7 refinements looked plausible on sampled frames but either broadened detections, overfragmented, or undercounted in the app path. Runtime event artifacts must be the authority for candidate settings.
2. **Tune tracker lifetime from measured split gaps, not from final totals.** v4 `max_age=180` hit the clean-cycle total but delayed counts too much to trust. Inspecting the actual duplicate windows showed gaps of about `4.5-5.3s`, which made `max_age=52` a much tighter candidate.
3. **High-confidence false/split detections rule out simple threshold fixes.** The bad approach fragment around `464.19s` was high-confidence while some likely true placements were lower-confidence, so confidence tightening would trade false positives for missed truth.
4. **A mid-placement opener must stay a product decision, not a model accident.** IMG_3254 can be treated as clean-cycle `22` or operational `23`; lock that rule before final proof rather than letting whichever setting happens to count the opener define truth.

## 2026-05-02: Validation Productization Lessons

1. **The registry should carry the current proof map.** If a future developer has to reconstruct case status from `.hermes`, `tasks/todo.md`, or a pile of report filenames, the validation process is still too ad hoc.
2. **Manifests are the right place for video-specific settings.** Model path, truth rule, launch command, event parameters, proof artifacts, and promotion status belong in `validation/test_cases/*.json`, not in memory or one-off command history.

3. **GitHub is the brain, not the warehouse.** Store validation manifests, detector cards, schemas, small reports, and hashes in GitHub. Store raw factory videos, full frame dumps, large model libraries, and embedding databases in `/Users/thomas/FactoryVisionArtifacts` first, with later Cloudflare R2/Backblaze B2 sync only after explicit permission. Every durable heavy artifact needs a path plus SHA-256 in `validation/artifact_storage.json` or the relevant case manifest.
3. **Do not move research scripts until imports/tests move with them.** The repo needs a cleaner script tree, but mechanically relocating top-level Factory2 scripts without shims would break existing tests. Mark the product path first, then move research scripts in a separate import-safe pass.
4. **Known limitations increase credibility.** Explicitly documenting that file-backed live validation is not yet live RTSP/Reolink validation makes the repo more trustworthy, not weaker.

## 2026-05-02: AI-Only Active Learning Boundary

1. **Active learning must not blur runtime authority.** Evidence windows, teacher labels, Moondream, Lens, and human/VA review are offline helpers; Runtime Total must still come from the YOLO/event app path without waiting for humans or VLMs.
2. **Teacher labels are poisoned truth until promoted.** Raw frontier/VLM suggestions start as `bronze` and `pending`. Validation tooling should reject them as truth rather than relying on filenames or reviewer memory.
3. **Dataset safety belongs in tooling, not policy text alone.** Train/test leakage and unreviewed gold labels need executable checks before any future active-learning dataset feeds model promotion.

## 2026-05-02: IMG_2628 Candidate Lessons

1. **Total-only truth is still a blocker, even when the total is trusted.** IMG_2628 starts with a human reference total of `25`, but without reviewed timestamps it can only support diagnostics and review packets, not promotion.
2. **Detector transfer can fail silently across visually similar press-brake videos.** IMG_3254/IMG_3262 active-panel models had near-zero sampled-frame recall on IMG_2628, so do a sampled detector screen before spending time on full app runs.
3. **A static detector cannot be tuned into proof by final-total pressure.** `wire_mesh_panel.pt` saw every sampled IMG_2628 frame; short lifetimes overcounted static fragmentation, while aggressive clustering/lifetimes undercounted. That is evidence for a new reviewed active-panel detector, not permission to keep nudging until the final number happens to be `25`.
4. **Moondream review queues are useful even when validation blocks.** Local MD2 generated an advisory review queue for the least-bad diagnostic windows, but all labels remained `bronze`/`pending`, `validation_truth_eligible=false`, and `training_eligible=false`.
5. **For long HEVC review scans, avoid random seek per timestamp.** A 1 fps CV-motion draft pass that used OpenCV `CAP_PROP_POS_MSEC` for every sampled second burned minutes on `IMG_2628`; the same advisory scan should use sequential ffmpeg decoding and reserve random seeks only for a small number of candidate contact strips.
6. **Separate operator frustration from proof boundaries.** When the user asks why Moondream or human review is slowing things down, explain the split plainly: runtime counting can and should keep moving without Moondream, while promotion truth still needs reviewed event evidence.
7. **A total-clean diagnostic can still hide event swaps.** The IMG_2628 worksheet detector reached `25/25` total, but draft-ledger comparison showed missing and unexpected events. Treat that as a candidate for visible operational review, not as event-level validation.
8. **When a user gives a trusted total, do the timestamp reconciliation work instead of bouncing it back by default.** For IMG_2628, the right move after the visible app hit `25` was focused dispute review against frames/contact sheets, then an auditable reviewed ledger. Keep Moondream out of truth, but do not make the user manually fill timestamps when local evidence can settle the disagreement.
9. **Manifest launch reconstruction must include every runtime knob.** IMG_2628 needed `event_track_max_match_distance=260`; the validation orchestrator initially omitted it from reconstructed launch commands. Add tests for any new manifest runtime setting that affects reproducibility.
10. **A lesson is not learned until it changes the next-video command path.** Notes alone did not make IMG_2628 faster. Reusable learning now needs either a script, manifest default, test, or runbook gate. `scripts/bootstrap_video_candidate.py` and `scripts/screen_detector_transfer.py` are the first explicit fast-path hooks for that rule.

## 2026-05-02: real_factory Blind Validation Lessons

1. **Blind bootstrap needs first-class tooling.** If the human total is intentionally hidden, candidate bootstrap must allow `expected_total=null` and mark `blind_estimate_pending_human_reveal`; forcing a numeric total invites fabricated truth.
2. **Static detector diagnostics are parameter-sensitivity probes, not count authority.** On `real_factory.MOV`, `wire_mesh_panel.pt` detected `80/80` sampled frames and the same app path shifted from `27` non-EOF events at `30s` debounce to `18` at `60s`. That swing is evidence to stop before visible proof and build/review a real active-part detector path.
3. **Bronze-anchor recovery must stay diagnostic unless truth is reviewed.** A `real_factory` model trained from draft visual anchors plus hard negatives can recover the app runtime count path, but it remains non-promotion evidence. Record the model/dataset boundary and keep `validation/registry.json` untouched until reviewed timestamp truth and eligible labels exist.
4. **Minimum track duration should reject measured transients, not chase totals.** The `real_factory` v2 detector counted four sustained tracks plus one 18-frame late false track at `min_frames=12`; setting `min_frames=30` rejected that measured transient while preserving tracks of `98`, `34`, `165`, and `70` frames.

### Training & Deployment Lessons

11. **ONNX export provides no speedup on i7-12700F.** PyTorch already runs at ~60ms/frame. ONNX overhead (model loading, conversion) wasn't worth it for this CPU. Don't bother unless moving to ARM/edge devices.
12. **Roboflow auto-label works for common shapes but NOT wire mesh.** Grounding DINO + SAM struggles with niche industrial objects. Manual labeling is required. Budget time accordingly.
13. **Camera angle matters critically.** Overhead/high angle reduces occlusion from worker's body. Side angle causes worker to block the panel during transit, killing recall.
14. **Kenneth at RMFG: shipped with 60 images, iterated.** Deploy imperfect, improve with production data. Don't wait for perfect model — correction buttons cover the gap.
15. **Training is fast on CPU.** YOLOv8n fine-tuning: ~20 min for 25 epochs on i7-12700F. No GPU needed for small datasets.
