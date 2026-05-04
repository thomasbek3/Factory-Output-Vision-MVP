## Decision

Use the strongest frontier vision model as an **optional teacher first** when cloud use is explicitly allowed. Do **not** use Moondream base/Lens as the first or only labeling source for new factories. The best strategy for this repo is:

```text
frontier/local VLM teacher suggestions
  -> human review / correction / lock
  -> gold labels + reviewed truth ledgers
  -> YOLO/event model training and evaluation
  -> real app rerun
  -> registry validation proof
```

Moondream should be used in parallel as a **local audit/triage model** and later as a **Lens feasibility target**, but not as the authority that creates truth. YOLO/event tracking remains the only runtime count path. Teacher labels remain bronze suggestions until a human/reconciler promotes them. That matches the repo’s current boundary: active learning artifacts are advisory, teacher labels are not validation truth, and real app proof must match reviewed human truth through the YOLO/event app path.

The nuance: current Moondream Station support in the repo is fine as a localhost-gated legacy/local adapter, but Moondream’s own Station page now says Station is deprecated and recommends Photon instead. Photon is the Moondream runtime to plan around next for local/on-prem inference. ([Moondream][1])

## Why frontier teacher first is the right call

Labeling is expensive because the human needs to find the few meaningful placement moments inside long factory video, distinguish static material from actual completed placement, and draw or confirm boxes/points. A strong frontier VLM can accelerate the **search and first-pass structure**. It should not create ground truth.

OpenAI’s current API docs support image input, multiple images per request, and structured outputs that adhere to a supplied JSON Schema; the current models page lists GPT-5.5 as the flagship model and says latest OpenAI models support text/image input and vision. ([OpenAI Platform][2]) Gemini’s current docs also support multimodal image/video-style inputs, structured JSON output, and Gemini 3.1 Pro Preview for complex multimodal tasks. ([Google AI for Developers][3]) Claude supports image analysis and strict tool/schema-style outputs through tool use, so it can be a viable teacher adapter too, especially for cross-checking. ([Claude API Docs][4])

But for the actual product, the provider choice should be abstracted. The repo should not become “GPT-4o labels” or “Gemini labels.” It should become:

```text
teacher_provider = openai | gemini | anthropic | moondream_photon | moondream_station_legacy | dry_run_fixture
teacher_output = bronze structured suggestion
human_review_output = gold/silver/bronze reviewed label
runtime_authority = YOLO/event app path only
```

## Cloud teacher vs local/on-prem rule

Default remains:

```text
privacy_mode = offline_local
cloud_upload_allowed = false
```

Cloud teacher models are acceptable only for **customer-approved setup/labeling work**, not silent production use. Acceptable cases:

```text
- internal demo footage
- customer explicitly approves cloud-assisted setup
- customer approves sending selected frames/clips, not raw full video
- footage has been cropped/redacted where practical
- provider, model, prompt version, request time, frame hashes, and permission id are recorded
- outputs are stored as bronze suggestions only
```

Local/on-prem is required when:

```text
- no written/customer-approved cloud permission exists
- footage includes sensitive process details, faces, badges, screens, customer IP, or regulated operations
- the customer contract says no cloud
- the footage is from live production and not designated for setup review
- the task is validation proof, runtime counting, or model promotion proof
```

Moondream/Photon is the right local/on-prem VLM direction. Moondream’s docs describe Moondream 3 Preview as the default for cloud API and local processing with Photon, with vision skills including object detection, pointing/counting, VQA, and captioning. ([Moondream Docs][5]) Photon supports local inference on edge/workstation/server/private-cloud hardware and says images, prompts, and inference stay on your hardware, although API key/billing telemetry may still exist. ([Moondream][6])

Important Lens caveat: Moondream finetuning currently says training runs in Moondream Cloud. So Lens is not compatible with a strict “no cloud ever” customer unless that customer approves the training upload path. After a finetune exists, Moondream docs say finetuned models can be used locally with Photon by referencing the finetune id/step. ([Moondream Docs][7])

## The architecture to productize

### Local artifact root

Keep Git as the brain/index and `/Users/thomas/FactoryVisionArtifacts` as the artifact warehouse.

Recommended storage layout:

```text
/Users/thomas/FactoryVisionArtifacts/
  videos/
    raw/
      {video_sha256}/source.MOV
    proxies/
      {case_id}/review_720p.mp4
    clips/
      {case_id}/{window_id}/
  frames/
    review/
      {case_id}/{evidence_id}/{window_id}/frame_00_*.jpg
    training/
      {dataset_id}/images/
  evidence/
    {case_id}/
      {evidence_id}.event_evidence.json
      {evidence_id}.candidate_windows.json
  teachers/
    {case_id}/
      {teacher_run_id}.teacher_labels.json
      prompts/{prompt_version}.json
  reviews/
    {case_id}/
      {review_batch_id}.review_queue.json
      {review_batch_id}.review_queue.html
      {review_batch_id}.review_labels.json
      {review_batch_id}.review_session_metrics.json
  labels/
    {case_id}/
      gold/
        event_ledger.reviewed_v*.json
        yolo_boxes.reviewed_v*.jsonl
        window_labels.reviewed_v*.jsonl
      silver/
      bronze/
  datasets/
    {dataset_id}/
      manifest.json
      yolo/
        images/train/
        images/val/
        images/test/
        labels/train/
        labels/val/
        labels/test/
      coco/
      exports/
  models/
    yolo/
      {model_id}/
        weights/best.pt
        weights/last.pt
        model_card.json
        train_report.json
        eval_report.json
        runtime_eval_report.json
    moondream/
      {lens_id}/
        lens_card.json
        eval_report.json
  runs/
    app/
      {run_id}/
        app_config.json
        observed_events.json
        app_vs_truth.json
        pacing.json
        screenshots/
        runtime_logs/
  promotions/
    {promotion_id}.json
  embeddings/
  backups/
```

Repo paths should store only indexes, schemas, docs, scripts, tests, and small reports:

```text
validation/
  registry.json
  artifact_storage.json
  learning_registry.json
  datasets/
    {dataset_id}.json
  detectors/
    {model_id}.json
  teachers/
    provider_configs.example.json
  cloud_permissions/
    {permission_id}.json
  schemas/
    ...
docs/
scripts/
tests/
```

## Lifecycle stages and what to call each artifact

Use consistent lifecycle names. This will keep the library from turning into a junk drawer.

```text
1. video_intake
   Artifact: video_manifest / candidate manifest
   Meaning: video copied, hashed, ffprobed, privacy mode set.

2. detector_transfer_screen
   Artifact: detector_transfer_screen
   Meaning: existing detectors tested for rough transfer. This is not proof.

3. runtime_diagnostic_run
   Artifact: app_run / observed_events
   Meaning: app attempted with candidate settings. Can fail. Failure is useful.

4. candidate_window_mining
   Artifact: candidate_windows / event_evidence
   Meaning: windows around runtime events, possible misses, false positives, motion spikes, hard negatives.

5. teacher_label_run
   Artifact: teacher_labels
   Meaning: VLM suggestions only. Bronze. Pending. Never truth.

6. human_review_batch
   Artifact: review_queue + review_labels
   Meaning: human/VA/reconciler approves, edits, rejects, or marks unclear.

7. gold_label_set
   Artifact: gold event ledger, gold boxes, gold window labels
   Meaning: human-approved labels eligible for training/eval; only timestamp truth ledgers can support validation.

8. dataset_assembly
   Artifact: dataset_manifest
   Meaning: train/val/test split, source hashes, label tiers, leakage checks.

9. model_train_run
   Artifact: train_report + model checkpoint
   Meaning: YOLO or Moondream Lens training experiment.

10. model_eval_run
    Artifact: eval_report
    Meaning: held-out frame/window/video evaluation, not runtime proof.

11. app_proof_run
    Artifact: observed_events + comparison + pacing + screenshots
    Meaning: real app/dashboard proof at 1.0x.

12. model_promotion
    Artifact: detector_card + promotion_report
    Meaning: safe to use as default or candidate model for a product/camera/factory.
```

## Data flow for a new candidate video

For `real_factory.MOV`, the flow should be:

```text
raw video
  -> intake + hash + privacy classification
  -> detector transfer screen
  -> failed detector transfer recorded
  -> candidate window mining from:
       motion windows
       bad runtime events
       suspected false positives
       suspected misses
       static/background negatives
       human-marked true event windows
  -> optional frontier/local teacher labels
  -> review queue
  -> human locks:
       4 true timestamp events
       false-positive windows from the 18-count failure
       hard negatives around static material
       YOLO boxes/points for active product states
  -> dataset assembly
  -> YOLO training
  -> detector eval
  -> accelerated runtime diagnostic
  -> visible 1.0x app proof only when diagnostic is plausible
  -> registry promotion only if app-vs-truth is clean
```

For the specific failure you described, the learning value is huge:

```text
real_factory:
  human total = 4
  failed diagnostic = 18
  delta = +14
```

Those 14+ false-positive/static-fragmentation windows should become reviewed hard negatives. Do not throw them away. But do not let them contaminate truth.

## Prompt and schema design

Add a provider-neutral teacher prompt schema. The teacher should see a small, deterministic review packet: usually 3 to 7 frames around a window, not the whole raw video unless explicitly approved.

### Add schema

```text
validation/schemas/teacher_prompt.schema.json
validation/schemas/candidate_window.schema.json
validation/schemas/teacher_eval_report.schema.json
validation/schemas/review_session.schema.json
validation/schemas/yolo_box_label.schema.json
validation/schemas/yolo_dataset_manifest.schema.json
validation/schemas/model_card.schema.json
validation/schemas/model_promotion_report.schema.json
validation/schemas/cloud_permission.schema.json
validation/schemas/review_speedup_report.schema.json
```

### Teacher output should look like this

```json
{
  "schema_version": "factory-vision-teacher-labels-v2",
  "case_id": "real_factory_candidate",
  "teacher_run_id": "real_factory_openai_gpt55_prompt_v3_20260503",
  "privacy_mode": "cloud_assisted_setup",
  "cloud_permission_id": "permission_customer_x_setup_20260503",
  "provider": {
    "name": "openai",
    "model": "gpt-5.5",
    "mode": "cloud_api",
    "prompt_version": "factory_event_teacher_v3",
    "network_calls_made": true
  },
  "refuses_validation_truth": true,
  "labels": [
    {
      "label_id": "real_factory-w003-teacher",
      "window_id": "real_factory-w003",
      "teacher_output_status": "static_stack",
      "suggested_event_ts_sec": null,
      "confidence_tier": "medium",
      "duplicate_risk": "low",
      "miss_risk": "unknown",
      "countable_under_rule": false,
      "placement_phase": "not_countable",
      "object_state": "static_resident_material",
      "bbox_normalized_xyxy": null,
      "point_normalized_xy": null,
      "evidence_frame_ids": ["frame_00", "frame_01", "frame_02"],
      "rationale": "Visible material appears static across the sampled frames; no completed placement is visible.",
      "label_authority_tier": "bronze",
      "review_status": "pending",
      "validation_truth_eligible": false,
      "training_eligible": false
    }
  ]
}
```

### Prompt rules

The prompt must be strict and boring:

```text
You are labeling candidate windows for a factory output counter.

Count rule:
Count one completed placement when the worker finishes putting the finished product in the output/resting area.

Do not count:
worker motion, machine motion, walking, touching/repositioning, static stacks, pallets,
partial handling, duplicate views, motion alone, resident material already present.

Return JSON only.
Use the supplied schema.
Do not create validation truth.
Do not set gold labels.
Do not invent timestamps outside the window.
Use unclear instead of guessing.
If the object is already resting and no placement completion is visible, classify static_stack.
If the worker is carrying/placing but completion is not visible yet, classify in_transit.
If completion is visible, classify completed and provide suggested_event_ts_sec within the window.
```

The teacher can suggest a box/point, but only a human-approved or reconciled label becomes training-eligible.

## Human review rules

The reviewer workflow should avoid anchoring. The reviewer should see the frames and count rule first; teacher output should be collapsed by default or shown after the reviewer makes a first decision.

Gold promotion rules:

```text
A label can become gold only when:
  - reviewer.type is human, va, or reconciled
  - review_status is approved or edited
  - approved_status is not null
  - frame hashes match the source evidence
  - video_sha256 matches the candidate manifest
  - the count rule is attached
  - reviewer id and reviewed_at are present
```

Validation truth rules are stricter:

```text
A validation truth ledger requires:
  - predeclared count rule
  - expected total
  - timestamped truth events
  - event ids in order
  - reviewer/reconciler metadata
  - validation_truth_eligible = true
  - no teacher provider as authority
```

Training labels can be:

```text
gold: allowed for YOLO training/eval and validation support if timestamp truth ledger
silver: allowed only for experiments, never validation
bronze: review queue only
```

For this repo, start YOLO training with **gold only**. Silver can come later after the guardrails are boringly reliable.

## How to avoid poisoning the dataset

The hard rule:

```text
teacher labels never enter validation truth
teacher labels never become training labels without human review
```

Productize that with these guardrails:

```text
1. Separate directories:
   labels/bronze, labels/silver, labels/gold

2. Separate schema fields:
   label_authority_tier
   review_status
   validation_truth_eligible
   training_eligible
   source_authority
   teacher_run_id
   reviewer_id

3. Immutable source hashes:
   video_sha256
   frame_sha256
   evidence_window_hash
   prompt_version
   provider_model

4. Dataset assembly filter:
   default --min-tier gold
   default --exclude-review-status pending,rejected,unclear
   default --reject-bronze
   default --reject-silver-for-validation

5. Leakage checks:
   no same window in train/test
   no same event neighborhood across train/test
   no same video_sha in both train and final validation unless explicitly marked customer-specific regression
   no frames from registry validation proof cases in train split unless the dataset manifest says they are training-only and not used for proof

6. Poisoning checks before train and before validation:
   scripts/check_dataset_poisoning.py
   scripts/check_learning_leakage.py
   scripts/validation_truth_guard.py
```

The false positives from `real_factory` should be valuable **hard negatives**, but only after a reviewer marks them as false positives/static/worker-only. The teacher can help rank them; it cannot launder them into truth.

## Runtime vs training vs validation truth

Use this vocabulary everywhere:

```text
runtime_observed_event:
  What the app counted.
  Source: FastAPI/VisionWorker/YOLO/event runtime.
  Authority: observed app behavior only.
  Not truth.

teacher_label:
  What a VLM suggested.
  Source: OpenAI/Gemini/Claude/Moondream/etc.
  Authority: bronze advisory only.
  Not truth.

review_label:
  What a human/VA/reconciler decided for a window/frame.
  Source: human review.
  Authority: training/eval if gold.
  Not automatically validation truth.

training_truth:
  Human-approved boxes/window labels/events used for model training/eval.
  Source: gold review labels.
  Authority: supervised training/eval.

validation_truth:
  Locked timestamped human truth ledger for a case.
  Source: reviewed/reconciled count ledger.
  Authority: app proof comparison.

model_eval:
  Offline detector/model performance.
  Source: held-out gold data.
  Authority: model screening only.

app_proof:
  Visible 1.0x real app run against validation truth.
  Source: runtime events + comparison + pacing.
  Authority: product validation.
```

## Model promotion

Add detector cards and promotion reports.

```text
validation/detectors/
  yolo_real_factory_active_product_v1.json
  yolo_factory2_img2628_img3254_img3262_merged_v1.json
```

A detector card should contain:

```json
{
  "schema_version": "factory-vision-detector-card-v1",
  "model_id": "yolo_real_factory_active_product_v1",
  "model_type": "yolov8n",
  "weights_artifact_relpath": "models/yolo/yolo_real_factory_active_product_v1/weights/best.pt",
  "training_dataset_id": "real_factory_gold_active_product_v1",
  "training_label_tiers": ["gold"],
  "excluded_validation_case_ids": [],
  "intended_use": "runtime_detector_candidate",
  "not_allowed_for": ["validation_truth", "teacher_truth"],
  "runtime_settings": {
    "counting_mode": "event_based",
    "demo_count_mode": "live_reader_snapshot"
  },
  "eval_reports": [],
  "promotion_status": "candidate"
}
```

Promotion gate:

```text
1. Dataset poisoning check passes.
2. Split leakage check passes.
3. Offline YOLO eval passes minimum recall/precision on held-out gold frames.
4. Accelerated runtime diagnostic is plausible.
5. Visible 1.0x app run is clean:
   matched_count == expected_total
   missing_truth_count == 0
   unexpected_observed_count == 0
   first_divergence == null
   wall_per_source near 1.0
6. Existing registry cases still pass if shared runtime/settings changed.
7. Model card and promotion report are written.
```

Do not promote a detector because it “looks better.” Promote only because it survives the app proof path.

## Measuring whether teacher labeling actually speeds validation

Add review metrics. Otherwise you will fool yourself.

Add:

```text
validation/schemas/review_speedup_report.schema.json
scripts/measure_review_speedup.py
```

Track per review batch:

```json
{
  "schema_version": "factory-vision-review-speedup-report-v1",
  "case_id": "real_factory_candidate",
  "review_batch_id": "real_factory_review_batch_v1",
  "teacher_run_id": "real_factory_openai_gpt55_prompt_v3",
  "baseline_mode": "manual_no_teacher",
  "teacher_mode": "teacher_ranked_queue",
  "windows_reviewed": 120,
  "gold_positive_events_found": 4,
  "gold_hard_negatives_found": 38,
  "human_minutes_total": 52.0,
  "human_minutes_per_gold_positive": 13.0,
  "teacher_accept_rate": 0.62,
  "teacher_edit_rate": 0.21,
  "teacher_reject_rate": 0.17,
  "unclear_rate": 0.08,
  "schema_valid_rate": 1.0,
  "cost_usd": 14.20,
  "speedup_vs_baseline": 1.7
}
```

Acceptance criteria for using a teacher provider repeatedly:

```text
- 0 cloud calls without permission
- 0 schema-invalid outputs after parser repair policy
- 0 teacher labels marked validation_truth_eligible
- 0 bronze labels included in training dataset
- review queue improves gold-label yield/hour by at least 1.5x after two candidate videos
- teacher-human agreement is measured by class, not guessed
- false-positive classes are preserved as hard negatives after human review
```

For `real_factory`, the first speed target is simple:

```text
Can the teacher-ranked queue help a human find and lock the 4 true events faster than reviewing the 29.5-minute video linearly?
```

If not, the teacher path is not paying for itself yet.

## How this affects Moondream Lens feasibility

Lens becomes more feasible **because** you use a frontier teacher + human review first. Lens needs high-quality task-specific labels. Starting Lens from raw/teacher-only labels would train it on noise.

Recommended Lens plan:

```text
Phase 0: Local Moondream/Photon baseline
  - Run Moondream base/Photon on the same evidence windows.
  - Compare to frontier teacher and human gold.
  - Do not train yet.

Phase 1: Gold dataset creation
  - Use frontier/local teachers only to accelerate review.
  - Human locks gold labels.
  - Build dataset with countable/completed/in_transit/static_stack/worker_only/unclear plus boxes/points where useful.

Phase 2: Lens experiment
  - Train Lens only on human-reviewed gold labels.
  - If using Lens cloud training, require customer permission because Moondream docs say finetuning runs in Moondream Cloud.
  - Evaluate on held-out factories/products/cameras.

Phase 3: Local deployment feasibility
  - Load fine-tune locally with Photon where allowed.
  - Use it for offline audit/review triage.
  - Never use it as runtime_total authority.

Success criteria:
  - Lens/Photon reduces human review time by at least 30% vs no-teacher review.
  - Lens matches or beats Moondream base on held-out review windows.
  - Lens is good enough to replace expensive frontier calls for routine local labeling.
  - YOLO/event runtime proof still carries the product claim.
```

Bluntly: Lens is not the first move. It is the local-specialist follow-up after you have enough clean labels.

## Exact repo additions

### Docs to add/update

```text
docs/08_LEARNING_LIBRARY_ARCHITECTURE.md
docs/09_LABELING_TEACHER_AND_PRIVACY_POLICY.md
docs/10_MODEL_TRAINING_AND_PROMOTION.md
docs/11_REAL_FACTORY_FAILURE_LESSONS.md
```

Update:

```text
docs/00_CURRENT_STATE.md
docs/03_VALIDATION_PIPELINE.md
docs/06_AI_ONLY_ACTIVE_LEARNING_PIPELINE.md
docs/07_ARTIFACT_STORAGE.md
docs/KNOWN_LIMITATIONS.md
docs/REAL_APP_TEST_CASE_DEFINITION_OF_DONE.md
```

Specific note to add: Station is legacy/deprecated; Photon is the preferred Moondream local inference target.

### Registries/manifests to add

```text
validation/learning_registry.json
validation/datasets/real_factory_gold_active_product_v1.json
validation/detectors/yolo_real_factory_active_product_v1.json
validation/cloud_permissions/example.cloud_permission.json
validation/teachers/provider_configs.example.json
```

### Schemas to add

```text
validation/schemas/learning_registry.schema.json
validation/schemas/cloud_permission.schema.json
validation/schemas/candidate_window.schema.json
validation/schemas/teacher_prompt.schema.json
validation/schemas/teacher_label_v2.schema.json
validation/schemas/review_session.schema.json
validation/schemas/yolo_box_label.schema.json
validation/schemas/yolo_dataset_manifest.schema.json
validation/schemas/detector_card.schema.json
validation/schemas/model_train_report.schema.json
validation/schemas/model_eval_report.schema.json
validation/schemas/model_promotion_report.schema.json
validation/schemas/review_speedup_report.schema.json
validation/schemas/leakage_report.schema.json
```

### Scripts to add

```text
scripts/sync_artifact_root.py
scripts/build_learning_registry.py
scripts/mine_candidate_windows.py
scripts/run_vlm_teacher.py
scripts/check_cloud_permission.py
scripts/serve_review_queue.py
scripts/write_review_labels.py
scripts/lock_gold_labels.py
scripts/assemble_yolo_dataset.py
scripts/check_learning_leakage.py
scripts/train_yolo_detector.py
scripts/evaluate_detector_frames.py
scripts/evaluate_detector_runtime.py
scripts/promote_detector.py
scripts/measure_review_speedup.py
scripts/export_example_library_html.py
```

Keep existing scripts, but evolve them:

```text
scripts/teacher_generate_labels.py
  -> keep dry_run_fixture
  -> add provider interface or delegate to run_vlm_teacher.py

scripts/moondream_audit_events.py
  -> keep Station legacy
  -> add moondream_photon provider

scripts/check_dataset_poisoning.py
  -> add case/video/product/camera split leakage
  -> reject silver for validation
  -> reject cloud teacher artifacts without permission id

scripts/validate_video.py
  -> keep validation truth guard
  -> add explicit rejection for any truth ledger with source_authority=teacher
```

### Tests to add

```text
tests/test_learning_registry_schema.py
tests/test_cloud_permission_gate.py
tests/test_vlm_teacher_provider_no_cloud_by_default.py
tests/test_teacher_label_v2_schema.py
tests/test_review_label_gold_promotion.py
tests/test_lock_gold_labels_rejects_teacher_only.py
tests/test_assemble_yolo_dataset_excludes_bronze.py
tests/test_check_learning_leakage_by_video_sha.py
tests/test_model_card_promotion_gate.py
tests/test_promote_detector_requires_clean_registry_cases.py
tests/test_real_factory_stays_candidate_until_clean_proof.py
tests/test_moondream_photon_provider_local_only.py
tests/test_review_speedup_metrics.py
```

## Concrete command flow

### 1. Intake

```bash
.venv/bin/python scripts/bootstrap_video_candidate.py \
  --case-id real_factory_candidate \
  --video data/videos/from-pc/real_factory.MOV \
  --expected-total 4 \
  --manifest validation/test_cases/real_factory.json \
  --preview \
  --force
```

Then sync/check local artifact root:

```bash
.venv/bin/python scripts/sync_artifact_root.py \
  --case-id real_factory_candidate \
  --manifest validation/test_cases/real_factory.json \
  --artifact-root /Users/thomas/FactoryVisionArtifacts \
  --verify-hash \
  --force
```

### 2. Detector screening

```bash
.venv/bin/python scripts/screen_detector_transfer.py \
  --video data/videos/from-pc/real_factory.MOV \
  --model models/img2628_worksheet_accept_event_diag_v1.pt \
  --model models/img3254_active_panel_v4_yolov8n.pt \
  --model models/img3262_active_panel_v2.pt \
  --model models/panel_in_transit.pt \
  --model models/wire_mesh_panel.pt \
  --output data/reports/real_factory_detector_transfer_screen.v2.json \
  --force
```

### 3. Mine candidate windows

```bash
.venv/bin/python scripts/mine_candidate_windows.py \
  --case-id real_factory_candidate \
  --manifest validation/test_cases/real_factory.json \
  --observed-events data/reports/real_factory_app_observed_events.run8092.wire_mesh_conf025_cluster250_age52_min12_debounce60_speed16_blind_diag_v1.json \
  --detector-screen data/reports/real_factory_detector_transfer_screen.blind_v1.json \
  --include-motion \
  --include-hard-negatives \
  --output /Users/thomas/FactoryVisionArtifacts/evidence/real_factory_candidate/real_factory_candidate_windows.v1.json \
  --frame-output-dir /Users/thomas/FactoryVisionArtifacts/frames/review/real_factory_candidate/windows_v1 \
  --force
```

### 4. Optional cloud teacher, permission gated

```bash
.venv/bin/python scripts/run_vlm_teacher.py \
  --candidate-windows /Users/thomas/FactoryVisionArtifacts/evidence/real_factory_candidate/real_factory_candidate_windows.v1.json \
  --provider openai \
  --model gpt-5.5 \
  --privacy-mode cloud_assisted_setup \
  --cloud-permission validation/cloud_permissions/customer_real_factory_setup_2026-05-03.json \
  --prompt-version factory_event_teacher_v3 \
  --output /Users/thomas/FactoryVisionArtifacts/teachers/real_factory_candidate/openai_gpt55_teacher_v1.json \
  --force
```

If no cloud permission:

```bash
.venv/bin/python scripts/run_vlm_teacher.py \
  --candidate-windows /Users/thomas/FactoryVisionArtifacts/evidence/real_factory_candidate/real_factory_candidate_windows.v1.json \
  --provider moondream_photon \
  --endpoint local \
  --privacy-mode offline_local \
  --prompt-version factory_event_teacher_v3 \
  --output /Users/thomas/FactoryVisionArtifacts/teachers/real_factory_candidate/moondream_photon_teacher_v1.json \
  --force
```

### 5. Review queue

```bash
.venv/bin/python scripts/build_review_queue.py \
  --evidence /Users/thomas/FactoryVisionArtifacts/evidence/real_factory_candidate/real_factory_candidate_windows.v1.json \
  --teacher-labels /Users/thomas/FactoryVisionArtifacts/teachers/real_factory_candidate/openai_gpt55_teacher_v1.json \
  --output /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_queue.json \
  --force

.venv/bin/python scripts/export_review_queue_html.py \
  --queue /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_queue.json \
  --output /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_queue.html \
  --force
```

Then human writes reviewed labels:

```bash
.venv/bin/python scripts/write_review_labels.py \
  --queue /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_queue.json \
  --reviewer-id thomas \
  --output /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_labels.json \
  --force
```

### 6. Lock gold labels

```bash
.venv/bin/python scripts/lock_gold_labels.py \
  --case-id real_factory_candidate \
  --review-labels /Users/thomas/FactoryVisionArtifacts/reviews/real_factory_candidate/review_batch_v1.review_labels.json \
  --gold-event-ledger data/reports/real_factory_human_truth_ledger.reviewed_v1.json \
  --gold-box-labels /Users/thomas/FactoryVisionArtifacts/labels/real_factory_candidate/gold/yolo_boxes.reviewed_v1.jsonl \
  --gold-window-labels /Users/thomas/FactoryVisionArtifacts/labels/real_factory_candidate/gold/window_labels.reviewed_v1.jsonl \
  --force
```

### 7. Assemble YOLO dataset

```bash
.venv/bin/python scripts/assemble_yolo_dataset.py \
  --dataset-id real_factory_gold_active_product_v1 \
  --case-id real_factory_candidate \
  --gold-box-labels /Users/thomas/FactoryVisionArtifacts/labels/real_factory_candidate/gold/yolo_boxes.reviewed_v1.jsonl \
  --artifact-root /Users/thomas/FactoryVisionArtifacts \
  --output-manifest validation/datasets/real_factory_gold_active_product_v1.json \
  --min-tier gold \
  --force
```

### 8. Check poisoning/leakage

```bash
.venv/bin/python scripts/check_dataset_poisoning.py \
  --dataset validation/datasets/real_factory_gold_active_product_v1.json

.venv/bin/python scripts/check_learning_leakage.py \
  --dataset validation/datasets/real_factory_gold_active_product_v1.json \
  --registry validation/registry.json
```

### 9. Train/evaluate YOLO

```bash
.venv/bin/python scripts/train_yolo_detector.py \
  --dataset validation/datasets/real_factory_gold_active_product_v1.json \
  --model-id yolo_real_factory_active_product_v1 \
  --artifact-root /Users/thomas/FactoryVisionArtifacts \
  --base yolov8n.pt \
  --epochs 80 \
  --force

.venv/bin/python scripts/evaluate_detector_runtime.py \
  --case-id real_factory_candidate \
  --detector validation/detectors/yolo_real_factory_active_product_v1.json \
  --manifest validation/test_cases/real_factory.json \
  --output data/reports/real_factory_yolo_real_factory_active_product_v1.runtime_eval.json \
  --force
```

### 10. Real app proof only after diagnostics are plausible

```bash
.venv/bin/python scripts/validate_video.py \
  --manifest validation/test_cases/real_factory.json \
  --execute \
  --auto-start \
  --output data/reports/real_factory_candidate_validation_report.registry_v2.json \
  --force
```

## Minimal next milestones

### Milestone 1: Learning library skeleton

Build the artifact layout, learning registry, schemas, and sync script.

Acceptance:

```text
- raw videos stay out of Git
- every heavy artifact has hash + artifact_relpath
- real_factory appears as failed/candidate learning case, not registry proof
- tests validate learning_registry and artifact paths
```

### Milestone 2: Human review writeback

The current HTML queue is useful, but it does not persist review decisions. That is the most urgent missing product piece.

Acceptance:

```text
- review labels can be written and schema-validated
- teacher suggestions remain bronze
- human-approved labels can become gold
- teacher-only labels cannot become gold
- truth ledger cannot point at teacher artifacts
```

### Milestone 3: Dataset assembler + poisoning/leakage gates

Acceptance:

```text
- assemble YOLO dataset from gold labels only
- bronze excluded by default
- train/test leakage rejected
- validation truth cases protected
- real_factory false positives can become hard negatives only after human review
```

### Milestone 4: Provider-gated VLM teacher

Acceptance:

```text
- dry_run_fixture still works
- moondream_photon local provider works or is stubbed with tests
- openai/gemini/anthropic providers require cloud permission
- offline_local mode refuses all cloud calls
- provider/model/prompt/frame hashes are logged
```

### Milestone 5: real_factory recovery loop

Acceptance:

```text
- reviewed 4-event timestamp ledger exists
- reviewed false-positive/hard-negative set exists
- YOLO detector trained from reviewed labels
- accelerated diagnostic is plausible
- visible 1.0x app run is attempted only after plausibility
- registry remains untouched until proof is clean
```

### Milestone 6: Moondream Lens feasibility

Acceptance:

```text
- Lens experiment uses human-reviewed gold labels only
- cloud training permission is explicit if used
- held-out eval compares Moondream base, Lens, frontier teacher, and human gold
- Lens is evaluated as offline audit/labeling helper only
- no runtime_total dependency on Lens
```

## The blunt gap in the current design

You have validation discipline. You do **not** yet have a full learning system.

Right now the repo has the beginnings: registry, manifests, event evidence, teacher labels, review queue, poisoning guard. That is good. But the product still lacks the pieces that make “improves after every failure” real:

```text
- no durable learning_registry.json
- no persistent human review writeback path
- no gold label locking script
- no dataset assembler
- no YOLO training/eval/promotion cards
- no model lineage tied to runtime proof
- no cloud permission gate
- no review speedup measurement
- no local Photon provider
- no example library browser beyond static queue HTML
```

Productize those before adding more clever AI. The fastest path is not “better model first.” It is **better data plumbing first**, then frontier teacher acceleration, then human-locked gold, then YOLO/event proof.

[1]: https://moondream.ai/p/station "Moondream"
[2]: https://platform.openai.com/docs/guides/images-vision "Images and vision | OpenAI API"
[3]: https://ai.google.dev/gemini-api/docs/image-understanding "Image understanding  |  Gemini API  |  Google AI for Developers"
[4]: https://docs.anthropic.com/en/docs/build-with-claude/vision "Vision - Claude API Docs"
[5]: https://docs.moondream.ai/ "Overview | Moondream Docs"
[6]: https://moondream.ai/p/photon "Photon | Moondream"
[7]: https://docs.moondream.ai/finetuning/ "Overview | Moondream Docs"
