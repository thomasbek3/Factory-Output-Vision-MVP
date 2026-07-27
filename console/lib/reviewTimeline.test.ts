import { describe, expect, it } from "vitest";
import {
  isCountableSourceTime,
  sourceTimeToVideoSec,
  timelineDurationMatches,
  videoTimeToSourceMs,
} from "@/lib/reviewTimeline";

const paddedTimeline = {
  canonicalStartMs: 5_000,
  canonicalEndMs: 905_000,
  renditionStartMs: 0,
  renditionEndMs: 910_000,
};

describe("review rendition timeline", () => {
  it("maps padded rendition time to canonical source time", () => {
    expect(videoTimeToSourceMs(5, 910, paddedTimeline)).toBe(5_000);
    expect(videoTimeToSourceMs(905, 910, paddedTimeline)).toBe(905_000);
  });

  it("disables tally input in leading and trailing context", () => {
    expect(isCountableSourceTime(4_999, paddedTimeline)).toBe(false);
    expect(isCountableSourceTime(5_000, paddedTimeline)).toBe(true);
    expect(isCountableSourceTime(904_999, paddedTimeline)).toBe(true);
    expect(isCountableSourceTime(905_000, paddedTimeline)).toBe(false);
  });

  it("restores a source position into padded rendition time", () => {
    expect(sourceTimeToVideoSec(455_000, 910, paddedTimeline)).toBe(455);
  });

  it("accepts encoder variance but rejects a material duration mismatch", () => {
    expect(timelineDurationMatches(909.9, paddedTimeline)).toBe(true);
    expect(timelineDurationMatches(891.8, paddedTimeline)).toBe(false);
  });

  it("round-trips known canonical timestamps", () => {
    for (const sourceTimeMs of [5_000, 455_000, 904_999]) {
      const videoSec = sourceTimeToVideoSec(sourceTimeMs, 910, paddedTimeline);
      expect(videoTimeToSourceMs(videoSec, 910, paddedTimeline)).toBe(sourceTimeMs);
    }
  });
});
