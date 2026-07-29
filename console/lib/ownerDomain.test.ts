import { describe, expect, it } from "vitest";
import {
  deriveOutputAttribution,
  deriveVerificationFrontier,
  deriveVerifiedGoodUnits,
} from "@/lib/ownerDomain";

describe("ownerDomain", () => {
  it("excludes revoked owner events and applies scrap/rework corrections", () => {
    expect(
      deriveVerifiedGoodUnits({
        events: [
          { occurredAtMs: 100 },
          { occurredAtMs: 200 },
          { occurredAtMs: 300 },
        ],
        adjustments: [{ deltaGoodUnits: -1 }, { deltaGoodUnits: 2 }],
        latestVerificationIntervals: [
          {
            sourceStartMs: 0,
            sourceEndMs: 150,
            status: "verified",
          },
          {
            sourceStartMs: 150,
            sourceEndMs: 250,
            status: "coverage_revoked",
          },
          {
            sourceStartMs: 250,
            sourceEndMs: 400,
            status: "verified",
          },
        ],
      }),
    ).toBe(3);
  });

  it("counts events only inside explicitly verified timeline coverage", () => {
    expect(
      deriveVerifiedGoodUnits({
        events: [
          { occurredAtMs: 100 },
          { occurredAtMs: 200 },
          { occurredAtMs: 300 },
          { occurredAtMs: 400 },
        ],
        adjustments: [],
        latestVerificationIntervals: [
          { sourceStartMs: 0, sourceEndMs: 150, status: "verified" },
          {
            sourceStartMs: 150,
            sourceEndMs: 250,
            status: "timeline_untrusted",
          },
          {
            sourceStartMs: 250,
            sourceEndMs: 350,
            status: "no_published_coverage",
          },
          {
            sourceStartMs: 350,
            sourceEndMs: 450,
            status: "coverage_revoked",
          },
        ],
      }),
    ).toBe(1);
  });

  it("attributes output to a person only for a covered solo interval", () => {
    expect(
      deriveOutputAttribution({
        workerIds: ["worker-a"],
        cameraCoverageBps: 9_500,
        minimumSoloCoverageBps: 9_500,
      }),
    ).toEqual({ mode: "solo", workerId: "worker-a" });
    expect(
      deriveOutputAttribution({
        workerIds: ["worker-a", "worker-b"],
        cameraCoverageBps: 10_000,
        minimumSoloCoverageBps: 9_500,
      }),
    ).toEqual({ mode: "team", workerId: null });
  });

  it("keeps a contiguous verification frontier and marks later verified data", () => {
    expect(
      deriveVerificationFrontier({
        expectedStartMs: 0,
        intervals: [
          { sourceStartMs: 0, sourceEndMs: 100, status: "verified" },
          {
            sourceStartMs: 100,
            sourceEndMs: 200,
            status: "no_published_coverage",
          },
          { sourceStartMs: 200, sourceEndMs: 300, status: "verified" },
        ],
      }),
    ).toEqual({
      verifiedThroughMs: 100,
      hasGap: true,
      noPublishedCoverage: true,
      verifiedAfterGap: [{ sourceStartMs: 200, sourceEndMs: 300 }],
    });
  });

  it("ignores revoked coverage that ends before the project starts", () => {
    expect(
      deriveVerificationFrontier({
        expectedStartMs: 10_000,
        intervals: [
          {
            sourceStartMs: 0,
            sourceEndMs: 5_000,
            status: "coverage_revoked",
          },
          {
            sourceStartMs: 10_000,
            sourceEndMs: 20_000,
            status: "verified",
          },
        ],
      }),
    ).toEqual({
      verifiedThroughMs: 20_000,
      hasGap: false,
      noPublishedCoverage: false,
      verifiedAfterGap: [],
    });
  });
});
