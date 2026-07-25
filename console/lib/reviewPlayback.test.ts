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

  it("steps down to 1x when the requested rate throws", () => {
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
});
