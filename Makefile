.PHONY: install test test-backend test-frontend lint build docs-check hygiene run-backend run-frontend run-test-case-1 validate-video benchmark-onboarding record-stream propose-onboarding-events build-teacher-evidence-packets generate-teacher-verifications generate-teacher-verifications-cloud grade-teacher-labels propose-auto-boxes rehearse-autonomous-onboarding reconcile-state-diff fuse-teacher-verifications run-teacher-loop-benchmark register-test-cases

CASE_ID ?= img3254_clean22_candidate
BACKEND_PORT ?= 8080
FRONTEND_PORT ?= 5173
ONBOARDING_VIDEO ?= demo/demo_counter.mp4
STATION_ID ?= demo-counter-autopilot-v1
ONBOARDING_MINUTES ?= 5
STREAM_SOURCE ?= $(ONBOARDING_VIDEO)
RECORDING_OUTPUT_ROOT ?= /Users/thomas/FactoryVisionArtifacts/recordings
RECORDING_DURATION_SEC ?= 30
SEGMENT_MANIFEST ?= $(RECORDING_OUTPUT_ROOT)/$(STATION_ID)/segment_manifest.json
EVENT_PROPOSAL_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_event_proposals.json
TEACHER_PACKET_OUTPUT_DIR ?= data/reports/onboarding/$(STATION_ID)_teacher_evidence_packets
TEACHER_PACKET_MANIFEST ?= $(TEACHER_PACKET_OUTPUT_DIR)/teacher_evidence_manifest.json
TEACHER_VERIFICATION_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_teacher_verifications.json
STATE_DIFF_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_state_diff_reconciliation.json
TEACHER_FUSION_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_teacher_fusion.json
SILVER_DATASET_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_silver_training_candidates.json
TEACHER_LOOP_BENCHMARK_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_teacher_loop_benchmark.json
TEACHER_PROVIDER ?= codex_cli
TEACHER_BATCH_SIZE ?= 4
TRUTH_LEDGER ?= data/reports/factory2_human_truth_ledger.v1.json
TEACHER_GRADE_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_teacher_grade_vs_truth.json
AUTO_BOX_OUTPUT ?= data/reports/onboarding/$(STATION_ID)_auto_boxes.json
AUTO_BOX_WORK_DIR ?= data/reports/onboarding/$(STATION_ID)_auto_box_work
REHEARSAL_WORK_ROOT ?= /Users/thomas/FactoryVisionArtifacts/rehearsal
REHEARSAL_OUTPUT ?= data/reports/onboarding/autonomous_onboarding_rehearsal.json
REHEARSAL_PLAYBACK_SPEED ?= 8

install:
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

test: test-backend

test-backend:
	.venv/bin/python -m pytest tests/ -q

test-frontend: lint build

lint:
	cd frontend && npm run lint

build:
	cd frontend && npm run build

docs-check:
	.venv/bin/python scripts/check_repo_hygiene.py

hygiene: docs-check test-backend test-frontend

run-backend:
	.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $(BACKEND_PORT)

run-frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT)

run-test-case-1:
	.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173

validate-video:
	.venv/bin/python scripts/validate_video.py --case-id $(CASE_ID) --dry-run

benchmark-onboarding:
	.venv/bin/python scripts/benchmark_ai_onboarding.py --video $(ONBOARDING_VIDEO) --station-id $(STATION_ID) --minutes $(ONBOARDING_MINUTES) --output data/reports/onboarding/$(STATION_ID)_benchmark.json --work-dir data/reports/onboarding/$(STATION_ID)_work --force

record-stream:
	.venv/bin/python scripts/record_stream_segments.py --source "$(STREAM_SOURCE)" --station-id "$(STATION_ID)" --output-root "$(RECORDING_OUTPUT_ROOT)" --duration-sec $(RECORDING_DURATION_SEC)

propose-onboarding-events:
	.venv/bin/python scripts/propose_onboarding_events.py --segment-manifest "$(SEGMENT_MANIFEST)" --output "$(EVENT_PROPOSAL_OUTPUT)" --force

build-teacher-evidence-packets:
	.venv/bin/python scripts/build_teacher_evidence_packets.py --event-proposals "$(EVENT_PROPOSAL_OUTPUT)" --output-dir "$(TEACHER_PACKET_OUTPUT_DIR)" --force

generate-teacher-verifications:
	.venv/bin/python scripts/generate_teacher_verifications.py --packet-manifest "$(TEACHER_PACKET_MANIFEST)" --output "$(TEACHER_VERIFICATION_OUTPUT)" --force

generate-teacher-verifications-cloud:
	.venv/bin/python scripts/generate_teacher_verifications.py --packet-manifest "$(TEACHER_PACKET_MANIFEST)" --provider $(TEACHER_PROVIDER) --allow-cloud --batch-size $(TEACHER_BATCH_SIZE) --output "$(TEACHER_VERIFICATION_OUTPUT)" --force

grade-teacher-labels:
	.venv/bin/python scripts/grade_teacher_labels_vs_truth.py --teacher-labels "$(TEACHER_VERIFICATION_OUTPUT)" --truth-ledger "$(TRUTH_LEDGER)" --packet-manifest "$(TEACHER_PACKET_MANIFEST)" --segment-manifest "$(SEGMENT_MANIFEST)" --output "$(TEACHER_GRADE_OUTPUT)" --force

propose-auto-boxes:
	.venv/bin/python scripts/propose_auto_boxes.py --silver-dataset "$(SILVER_DATASET_OUTPUT)" --packet-manifest "$(TEACHER_PACKET_MANIFEST)" --work-dir "$(AUTO_BOX_WORK_DIR)" --output "$(AUTO_BOX_OUTPUT)" --force

rehearse-autonomous-onboarding:
	.venv/bin/python scripts/run_autonomous_onboarding_rehearsal.py --work-root "$(REHEARSAL_WORK_ROOT)" --output "$(REHEARSAL_OUTPUT)" --teacher-provider $(TEACHER_PROVIDER) --allow-cloud --teacher-batch-size $(TEACHER_BATCH_SIZE) --playback-speed $(REHEARSAL_PLAYBACK_SPEED) --force

reconcile-state-diff:
	.venv/bin/python scripts/reconcile_state_diff.py --packet-manifest "$(TEACHER_PACKET_MANIFEST)" --teacher-labels "$(TEACHER_VERIFICATION_OUTPUT)" --output "$(STATE_DIFF_OUTPUT)" --force

fuse-teacher-verifications:
	.venv/bin/python scripts/fuse_teacher_verifications.py --teacher-labels "$(TEACHER_VERIFICATION_OUTPUT)" --state-diff "$(STATE_DIFF_OUTPUT)" --silver-dataset "$(SILVER_DATASET_OUTPUT)" --output "$(TEACHER_FUSION_OUTPUT)" --force

run-teacher-loop-benchmark:
	.venv/bin/python scripts/run_teacher_loop_benchmark.py --event-proposals "$(EVENT_PROPOSAL_OUTPUT)" --teacher-labels "$(TEACHER_VERIFICATION_OUTPUT)" --fusion-report "$(TEACHER_FUSION_OUTPUT)" --output "$(TEACHER_LOOP_BENCHMARK_OUTPUT)" --force

register-test-cases:
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/factory2.json --force
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3262.json --force
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3254_clean22.json --force
