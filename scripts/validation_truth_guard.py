"""CLI/test compatibility wrapper for the validation truth guard.

Implementation lives in app.services.validation_truth_guard.
"""

from app.services.validation_truth_guard import (  # noqa: F401
    DISALLOWED_TRUTH_SCHEMA_VERSIONS,
    ValidationTruthError,
    iter_dicts,
    read_json,
    validate_truth_file,
    validate_truth_payload,
)
