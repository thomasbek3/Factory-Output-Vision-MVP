import { describe, expect, it } from "vitest";
import { gradeFinishedJob, nextTimeSuggestion } from "@/lib/historyRecords";

describe("history NEXT TIME math", () => {
  it("rounds the faster-job suggestion to the nearest half day", () => {
    const result = nextTimeSuggestion({
      client: "Ramirez",
      product: "wire panels",
      quotedDays: 4,
      actualDays: 3.4,
      plannedMarginUsd: 200,
      realMarginUsd: 264,
      bottleneckStation: "Pallet A",
    });

    expect(result.suggestDays).toBe(3.5);
    expect(result.delta).toBe(64);
    expect(result.sentence).toContain("Quote the next Ramirez wire panels order at 3.5 days");
  });

  it("uses the over-run sentence when actual days exceed quoted days", () => {
    const result = nextTimeSuggestion({
      client: "Delgado",
      product: "HVAC brackets",
      quotedDays: 2.5,
      actualDays: 3.9,
      plannedMarginUsd: 420,
      realMarginUsd: 112,
      bottleneckStation: "Gate line",
    });

    expect(result.suggestDays).toBe(4);
    expect(result.sentence).toContain("ran 56% over");
    expect(result.sentence).toContain("fix the bottleneck at Gate line");
  });
});

describe("finished-job grade boundaries", () => {
  const base = { quotedDays: 2, actualDays: 2, plannedMarginUsd: 100 };

  it("grades A at planned margin and on time", () => {
    expect(gradeFinishedJob({ ...base, realMarginUsd: 100 })).toBe("A");
  });

  it("grades B at the 80 percent planned-margin boundary", () => {
    expect(gradeFinishedJob({ ...base, actualDays: 4, realMarginUsd: 80 })).toBe("B");
  });

  it("grades C for positive margin below B thresholds", () => {
    expect(gradeFinishedJob({ ...base, actualDays: 4, realMarginUsd: 79 })).toBe("C");
  });

  it("grades C− for negative real margin", () => {
    expect(gradeFinishedJob({ ...base, actualDays: 1, realMarginUsd: -1 })).toBe("C−");
  });
});
