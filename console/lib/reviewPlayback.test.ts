import { describe, expect, it } from "vitest";
import {
  applyValidatedPlaybackRate,
  compensatedPlaybackTarget,
} from "@/lib/reviewPlayback";

describe("review playback rate", () => {
  it("keeps an accepted validated speed", () => {
    const media = { playbackRate: 1 };

    expect(applyValidatedPlaybackRate(media, 5)).toEqual({
      effectiveRate: 5,
      nativeRate: 5,
      compensated: false,
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
      nativeRate: 1,
      compensated: false,
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
      nativeRate: 2,
      compensated: false,
      steppedDown: true,
    });
    expect(effectiveRate).toBe(2);
  });

  it("bridges native 15x playback to an effective 20x mode", () => {
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
      effectiveRate: 20,
      nativeRate: 15,
      compensated: true,
      steppedDown: false,
    });
    expect(effectiveRate).toBe(15);
  });

  it("anchors compensated playback to elapsed wall time", () => {
    expect(compensatedPlaybackTarget(10, 20, 2_000, 900)).toBe(50);
    expect(compensatedPlaybackTarget(890, 20, 2_000, 900)).toBe(900);
    expect(compensatedPlaybackTarget(10, 20, -1, 900)).toBe(10);
  });
});

describe("high-speed review playback", () => {
  it("scales coverage tolerance with the selected playback rate", async () => {
    const { coverageGapToleranceMs } = await import("@/lib/reviewPlayback");
    expect(coverageGapToleranceMs(1)).toBe(3_000);
    expect(coverageGapToleranceMs(20)).toBe(12_000);
  });
});
