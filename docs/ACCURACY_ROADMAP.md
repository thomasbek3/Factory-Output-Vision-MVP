# Accuracy Roadmap — Enterprise-Grade Counting

## Current State (2026-03-19)
- Custom YOLOv8n model detects panels in transit (being carried by worker)
- CentroidTracker assigns persistent IDs, track death = +1 count
- 82 training images, 83% recall, 87% precision, 81% mAP50
- 23/23 accuracy on factory2.MOV offline scan
- Real-time: ~23 counts but some double-counts and missed counts cancel out (lucky accuracy, not real accuracy)

## Tier 1 — Build Now (Next 2 Weeks)

### 1. Temporal Smoothing (Frame Voting)
**What:** Instead of binary detect/no-detect per frame, use a sliding window. If the model detects a panel in 3 out of 5 consecutive frames → "detected." If 1 out of 5 → "not detected."
**Kills:** Detection flicker that causes double-counts.
**Risk:** Adds slight latency. Might smooth out legitimate short detections.
**Effort:** ~1 hour of code.

### 2. Continuous Learning Pipeline (The Moat)
**What:** When operator presses +/-, save the current frame + detection state to Roboflow via API. Accumulate correction frames. Retrain weekly/monthly. Model improves specifically on its failure cases.
**Kills:** ALL failure modes over time. Every deployment makes the model better.
**Risk:** Need to build the pipeline (save, upload, retrain, redeploy). Operator corrections could be wrong occasionally.
**Effort:** ~1-2 days to build the pipeline.
**Why this is the moat:** No competitor does this. The model gets better with every factory deployment without engineering effort. Kenneth at RMFG uses this exact approach.

### 3. Cycle-Time Soft Filter
**What:** Learn the average cycle time from the first N counts. If a count fires way faster than expected (e.g., 3 seconds after the last count when typical is 15 seconds), lower its confidence. Don't hard-suppress — just flag it.
**Kills:** Obvious double-counts.
**Risk:** Workers speed up and slow down. Two quick legitimate carries could get incorrectly flagged.
**Effort:** ~2 hours of code.

## Tier 2 — Build Next Month

### 4. Track Trajectory Validation
**What:** After a track dies, validate: did the centroid move in a smooth carry-like path (A→B, minimum distance, consistent velocity)? Reject tracks with erratic or zero movement.
**Kills:** False positive tracks from random detection jitter.
**Risk:** Assumes clear A→B carry path. Tight workspaces with minimal movement may produce short trajectories. Needs factory layout awareness.
**Effort:** ~1 day of code.

### 5. Negative Mining from Corrections
**What:** Auto-collect frames where the model fires false positives (identified via operator -1 corrections). Add these as negative training examples. Retrain.
**Kills:** Recurring false positives. Model learns what ISN'T a panel in transit.
**Risk:** Need correct identification of false positives. Risk of training on noisy labels if corrections are wrong.
**Effort:** Builds on top of Continuous Learning Pipeline (#2). ~4 hours additional.

### 6. Dual-Model Confirmation (Optional)
**What:** Run panel detection AND person detection simultaneously. Count fires only when BOTH agree: panel detected AND person centroid is near the panel's bounding box.
**Kills:** Ghost detections from random objects when no worker is present.
**Risk:** Doubles compute (two YOLO passes per frame). On CPU, cuts effective FPS in half. Mostly redundant since the transit model already implies a person is present.
**Effort:** ~4 hours. Only build if false positives during idle are a real problem.

## Tier 3 — R&D Next Quarter

### 7. Action Recognition Model
**What:** Instead of detecting an OBJECT per frame, detect the ACTION of "placing a panel" from a 3-5 second video clip. Models like SlowFast, TimeSformer, or Video-MAE understand temporal dynamics — they see grab→carry→place as one event.
**Kills:** Everything. This is the right long-term answer. Detects the EVENT, not the OBJECT.
**Risk:** Larger models, slower inference, likely needs GPU (or Jetson edge device). Video clip labeling is harder than image labeling. Training is more complex. Significant R&D investment.
**Effort:** 2-4 weeks of R&D.
**Why it matters:** This approach is fundamentally more robust because it understands the complete motion, not just a snapshot. A single frame can be ambiguous. A 3-second clip is not.

### 8. Synthetic Data Generation
**What:** Generate thousands of training images by compositing wire mesh panel cutouts onto different factory backgrounds at various angles, sizes, and lighting conditions.
**Kills:** The need for manual labeling. Can generate rare scenarios (unusual angles, extreme lighting).
**Risk:** Domain gap — synthetic images never perfectly match real factory conditions. Supplements real data, doesn't replace it.
**Effort:** 1-2 weeks to build the generation pipeline.

### 9. Multi-Camera Fusion
**What:** Two cameras from different angles. A count requires confirmation from both cameras.
**Kills:** Occlusion completely. Single-camera blind spots become irrelevant.
**Risk:** 2x hardware cost. Camera synchronization is complex. Cross-camera calibration required. Overkill for most small factories.
**Effort:** 2-3 weeks. Enterprise-tier feature for high-value deployments only.

## What NOT to Build
- **Embedding-based dedup** — All wire mesh panels look identical. Visual embeddings can't distinguish "same panel re-detected" from "different panel." Dead end.
- **Periodic stack census** — Can't count individual panels in a stack. Stack of 20 looks like stack of 21 to the model. Dead end for stacked identical objects.
- **Frame differencing / blob detection** — Worker body dominates the signal. Person masking creates artifacts. Red-teamed and rejected (see tasks/lessons.md).
- **Count line crossing** — Requires precise placement, doesn't work for non-conveyor factories. Replaced by output zone approach.

## The Priority Order
1. More training data (ongoing) — every new factory video = better model
2. Continuous learning pipeline — the product moat
3. Temporal smoothing — quick win for flicker
4. Trajectory validation — structural fix for double-counts
5. Action recognition R&D — the endgame

## Key Principle
Don't chase 100% accuracy on day one. Build the system so it GUARANTEES improvement over time with minimal effort. The continuous learning loop is the product, not perfect accuracy.
