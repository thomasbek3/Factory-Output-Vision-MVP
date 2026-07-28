import { describe, expect, it } from "vitest";
import { applyValidatedPlaybackRate } from "@/lib/reviewPlayback";

describe("review playback rate", () => {
  it("keeps an accepted validated speed", () => {
    const media = { playbackRate: 1 };

    expect(applyValidatedPlaybackRate(media, 5)).toEqual({
      effectiveRate: 5,
      steppedDown: false,
    });
    expect(media.playbackRate).toBe(5);
  });

  it("walks down the validated ladder when faster rates throw", () => {
    let effectiveRate = 1;
    const media = {
      get playbackRate() {
        return effectiveRate;
      },
      set playbackRate(value: number) {
        if (value !== 1) throw new DOMException("unsupported", "NotSupportedError");
        effectiveRate = value;
      },
    };

    expect(applyValidatedPlaybackRate(media, 5)).toEqual({
      effectiveRate: 1,
      steppedDown: true,
    });
    expect(effectiveRate).toBe(1);
  });

  it("detects silent browser clamping and uses the next lower validated speed", () => {
    let effectiveRate = 1;
    const media = {
      get playbackRate() {
        return effectiveRate;
      },
      set playbackRate(value: number) {
        effectiveRate = value === 5 ? 4 : value;
      },
    };

    expect(applyValidatedPlaybackRate(media, 5)).toEqual({
      effectiveRate: 2,
      steppedDown: true,
    });
    expect(effectiveRate).toBe(2);
  });

  it("falls back to 15x when the browser rejects a native 20x rate", () => {
    let effectiveRate = 1;
    const media = {
      get playbackRate() {
        return effectiveRate;
      },
      set playbackRate(value: number) {
        if (value > 15) {
          throw new DOMException("unsupported", "NotSupportedError");
        }
        effectiveRate = value;
      },
    };

    expect(applyValidatedPlaybackRate(media, 20)).toEqual({
      effectiveRate: 15,
      steppedDown: true,
    });
    expect(effectiveRate).toBe(15);
  });
});

describe("high-speed review playback", () => {
  it("scales coverage tolerance with the selected playback rate", async () => {
    const { coverageGapToleranceMs } = await import("@/lib/reviewPlayback");
    expect(coverageGapToleranceMs(1)).toBe(3_000);
    expect(coverageGapToleranceMs(20)).toBe(12_000);
  });
});
