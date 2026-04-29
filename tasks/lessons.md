# Lessons Learned

## 2026-04-28: Factory2 Definition Of Done

1. **Proof-only success is not done.** If Factory2 counts in `scripts/run_factory2_morning_proof.py` but the actual worker/app runtime path still shows `counts_this_hour: 0`, the task is still in progress.
2. **Do not stop at diagnostics or receipts.** Diagnostics exist to unlock counting, not to replace it.
3. **For Factory2, verify the real product path.** Run the actual `VisionWorker`/FastAPI monitoring flow on `factory2.MOV`, not just unit tests or proof scripts.
4. **If stuck on the next move, escalate to Oracle before asking the user for direction.**

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

### Model Performance & Recall Requirements

4. **53% recall is insufficient for real-time event counting.** Sparse detections don't form reliable temporal clusters. Need 80%+ recall, which requires 150+ labeled training images (currently at 47).
5. **Offline scanning (seeking through video) works even with low recall.** When you can scan every frame, even 53% recall catches most events. Real-time streaming at 10 FPS with sparse detections misses clusters entirely. Real-time needs higher recall.
6. **Wire mesh panel model (v1): 98% precision, 91% recall, mAP50 94.6% with 71 images.** Great detection, but useless for counting — detects static stacks.
7. **Panel in transit model (v2): 94% precision, 53% recall with 47 images.** Promising but needs 3x more training data.

### Training & Deployment Lessons

8. **ONNX export provides no speedup on i7-12700F.** PyTorch already runs at ~60ms/frame. ONNX overhead (model loading, conversion) wasn't worth it for this CPU. Don't bother unless moving to ARM/edge devices.
9. **Roboflow auto-label works for common shapes but NOT wire mesh.** Grounding DINO + SAM struggles with niche industrial objects. Manual labeling is required. Budget time accordingly.
10. **Camera angle matters critically.** Overhead/high angle reduces occlusion from worker's body. Side angle causes worker to block the panel during transit, killing recall.
11. **Kenneth at RMFG: shipped with 60 images, iterated.** Deploy imperfect, improve with production data. Don't wait for perfect model — correction buttons cover the gap.
12. **Training is fast on CPU.** YOLOv8n fine-tuning: ~20 min for 25 epochs on i7-12700F. No GPU needed for small datasets.
