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
