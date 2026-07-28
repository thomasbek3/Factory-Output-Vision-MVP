import { describe, expect, it } from "vitest";
import {
  humanSubmissionValue,
  truthStatus,
} from "./ops-command-center";

type TruthInput = Parameters<typeof truthStatus>[0];

function label(overrides: Partial<TruthInput> = {}): TruthInput {
  return {
    chunkId: "chunk",
    factoryId: "factory",
    factoryName: "Factory",
    factoryTimezone: "America/New_York",
    stationId: "station",
    stationAlias: "Gate line",
    sourceStartAt: "2026-07-09T16:08:00Z",
    sourceEndAt: "2026-07-09T16:23:00Z",
    chunkState: "resolving",
    sourceSha256: "a".repeat(64),
    reviewRound: 1,
    submissionCount: 3,
    problemCount: 1,
    humanTotals: [],
    consensusStatus: "resolved",
    resolvedTotal: 10,
    supportCount: 2,
    consensusEventCount: 10,
    humanFinalAt: null,
    publicationCount: 0,
    exceptionType: null,
    exceptionReason: null,
    aiRunId: null,
    aiStatus: "not_run",
    aiCodeVersion: null,
    aiEventCount: 0,
    comparisonMetrics: null,
    comparisonCreatedAt: null,
    ...overrides,
  };
}

describe("ops truth presentation", () => {
  it("shows a resolved two-counts-plus-one-problem round awaiting finalization", () => {
    expect(truthStatus(label())).toEqual({
      text: "Resolved · awaiting final",
      tone: "info",
    });
    expect(
      humanSubmissionValue({ resultType: "problem", totalCount: null }),
    ).toBe("!");
  });

  it("only shows human final after finalization", () => {
    expect(
      truthStatus(label({ humanFinalAt: "2026-07-09T17:00:00Z" })),
    ).toEqual({ text: "Human final", tone: "good" });
  });
});
