import { RpcError } from "./reviewSupabase";

// Error-classification helpers for the worker portal UI. Kept out of the
// component so they can be unit-tested directly. Typed codes come from
// supabase/migrations/20260821190000_typed_coverage_gate_error_codes.sql;
// prose branches only fire for servers that predate that migration.

export function isAssignmentUnavailable(error: unknown) {
  if (error instanceof RpcError) {
    // MFA gate has its own typed code and must NOT read as "task expired".
    if (error.domainCode === "MFA_REQUIRED") return false;
    // Legacy fallback FIRST: pre-MF000 deployments raise bare 42501 for both
    // lease and MFA failures, so classify by prose before the wholesale
    // 42501 -> LEASE_UNAVAILABLE mapping can mislabel MFA.
    if (error.code === "42501" || error.domainCode === "UNKNOWN") {
      return /lease|assignment.*(?:unavailable|expired|not submittable)|access disabled/i.test(error.message);
    }
    return error.domainCode === "LEASE_UNAVAILABLE";
  }
  const message = error instanceof Error ? error.message : String(error);
  return /lease|assignment.*(?:unavailable|expired|not submittable)|access disabled/i.test(message);
}

export function isCoverageIncomplete(error: unknown) {
  if (error instanceof RpcError) {
    return (
      error.domainCode === "COVERAGE_MISSING" ||
      error.domainCode === "COVERAGE_INCOMPLETE" ||
      error.domainCode === "COVERAGE_TOO_FAST" ||
      // Legacy server: pre-typed-migration deployments raise bare 23514
      // (CHECK_VIOLATION) or carry no code at all (UNKNOWN).
      ((error.domainCode === "CHECK_VIOLATION" || error.domainCode === "UNKNOWN") &&
        /coverage|98 percent|faster than the enabled playback speed/i.test(error.message))
    );
  }
  const message = error instanceof Error ? error.message : String(error);
  return /coverage|98 percent|faster than the enabled playback speed/i.test(message);
}
