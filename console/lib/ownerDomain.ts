type OwnerVerificationStatus =
  | "verified"
  | "timeline_untrusted"
  | "no_published_coverage"
  | "coverage_revoked";

type OwnerVerificationInterval = {
  sourceStartMs: number;
  sourceEndMs: number;
  status: OwnerVerificationStatus;
};

export function deriveVerifiedGoodUnits(input: {
  events: readonly { occurredAtMs: number }[];
  adjustments: readonly { deltaGoodUnits: number }[];
  latestVerificationIntervals: readonly OwnerVerificationInterval[];
}) {
  const verified = input.latestVerificationIntervals.filter(
    (interval) => interval.status === "verified",
  );
  const publishedUnits = input.events.filter(
    (event) =>
      verified.some(
        (interval) =>
          event.occurredAtMs >= interval.sourceStartMs &&
          event.occurredAtMs < interval.sourceEndMs,
      ),
  ).length;
  const adjustment = input.adjustments.reduce(
    (sum, row) => sum + row.deltaGoodUnits,
    0,
  );
  return Math.max(0, publishedUnits + adjustment);
}

export function deriveOutputAttribution(input: {
  workerIds: readonly string[];
  cameraCoverageBps: number;
  minimumSoloCoverageBps: number;
}) {
  const workers = [...new Set(input.workerIds)];
  if (
    workers.length === 1 &&
    input.cameraCoverageBps >= input.minimumSoloCoverageBps
  ) {
    return { mode: "solo" as const, workerId: workers[0] };
  }
  return { mode: "team" as const, workerId: null };
}

export function deriveVerificationFrontier(input: {
  expectedStartMs: number;
  intervals: readonly OwnerVerificationInterval[];
}) {
  const sorted = [...input.intervals].sort(
    (left, right) =>
      left.sourceStartMs - right.sourceStartMs ||
      left.sourceEndMs - right.sourceEndMs,
  );
  let frontier = input.expectedStartMs;
  let hasGap = false;
  let noPublishedCoverage = false;
  const verifiedAfterGap: {
    sourceStartMs: number;
    sourceEndMs: number;
  }[] = [];

  for (const interval of sorted) {
    if (interval.sourceEndMs <= input.expectedStartMs) continue;
    if (interval.sourceStartMs > frontier) hasGap = true;
    if (interval.status !== "verified") {
      hasGap = true;
      noPublishedCoverage ||= interval.status === "no_published_coverage";
      continue;
    }
    if (hasGap || interval.sourceStartMs > frontier) {
      verifiedAfterGap.push({
        sourceStartMs: interval.sourceStartMs,
        sourceEndMs: interval.sourceEndMs,
      });
      continue;
    }
    frontier = Math.max(frontier, interval.sourceEndMs);
  }

  return {
    verifiedThroughMs: frontier,
    hasGap,
    noPublishedCoverage,
    verifiedAfterGap,
  };
}
