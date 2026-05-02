.PHONY: install test test-backend test-frontend lint build run-backend run-frontend run-test-case-1 validate-video register-test-cases

CASE_ID ?= img3254_clean22_candidate
BACKEND_PORT ?= 8080
FRONTEND_PORT ?= 5173

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

run-backend:
	.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $(BACKEND_PORT)

run-frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT)

run-test-case-1:
	.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173

validate-video:
	.venv/bin/python scripts/validate_video.py --case-id $(CASE_ID) --dry-run

register-test-cases:
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/factory2.json --force
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3262.json --force
	.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3254_clean22.json --force
