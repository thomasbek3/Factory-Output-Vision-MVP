#!/usr/bin/env bash
set -euo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "${CONSOLE_DIR}/.." && pwd)"
MIGRATION="${ROOT_DIR}/supabase/migrations/20260729070000_owner_v2_core.sql"
FIXTURE="${ROOT_DIR}/supabase/tests/owner_v2_live.sql"
SQL_FILE="$(mktemp)"
trap 'rm -f "${SQL_FILE}"' EXIT

: "${DATABASE_URL:?DATABASE_URL is required}"

python3 - "${MIGRATION}" "${FIXTURE}" "${SQL_FILE}" <<'PY'
from pathlib import Path
import sys

migration = Path(sys.argv[1]).read_text(encoding="utf-8")
fixture = Path(sys.argv[2]).read_text(encoding="utf-8")
output = Path(sys.argv[3])

function_start = migration.index(
    "create or replace function public.owner_scheduled_work_milliseconds"
)
function_end = migration.index(
    "create or replace function public.owner_save_project_draft",
    function_start,
)
fixture_start = fixture.index("do $$\ndeclare\n  fall_back_ms bigint;")
fixture_end = fixture.index("\n$$;", fixture_start) + len("\n$$;")

output.write_text(
    "\\set ON_ERROR_STOP on\n"
    "begin;\n"
    + migration[function_start:function_end]
    + "\n"
    + fixture[fixture_start:fixture_end]
    + "\nrollback;\n",
    encoding="utf-8",
)
PY

psql "${DATABASE_URL}" -X -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
printf 'OWNER_SCHEDULE_SQL_PASS\n'
