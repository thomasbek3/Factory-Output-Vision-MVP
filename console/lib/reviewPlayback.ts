const VALIDATED_PLAYBACK_RATES = [1, 2, 5, 10, 15, 20] as const;

export function applyValidatedPlaybackRate(
  media: Pick<HTMLMediaElement, "playbackRate">,
  requested: number,
) {
  const candidates = [
    requested,
    ...VALIDATED_PLAYBACK_RATES.filter((rate) => rate < requested).sort((a, b) => b - a),
  ];

  for (const candidate of [...new Set(candidates)]) {
    try {
      media.playbackRate = candidate;
      if (media.playbackRate === candidate) {
        return { effectiveRate: candidate, steppedDown: candidate !== requested };
      }
    } catch {
      // Try the next lower validated rate.
    }
  }

  media.playbackRate = 1;
  return { effectiveRate: 1, steppedDown: requested !== 1 };
}

export function coverageGapToleranceMs(playbackRate: number) {
  return Math.max(3_000, Math.ceil(playbackRate * 600));
}
