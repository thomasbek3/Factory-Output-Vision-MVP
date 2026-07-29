const VALIDATED_PLAYBACK_RATES = [1, 2, 5, 10, 15, 20] as const;
const NATIVE_20X_BRIDGE_RATES = [16, 15, 10] as const;

export function applyValidatedPlaybackRate(
  media: Pick<HTMLMediaElement, "playbackRate">,
  requested: number,
) {
  try {
    media.playbackRate = requested;
    if (media.playbackRate === requested) {
      return {
        effectiveRate: requested,
        nativeRate: requested,
        compensated: false,
        steppedDown: false,
      };
    }
  } catch {
    // Try a compensated native rate or the next lower worker-facing speed.
  }

  if (requested === 20) {
    for (const candidate of NATIVE_20X_BRIDGE_RATES) {
      try {
        media.playbackRate = candidate;
        if (media.playbackRate === candidate) {
          return {
            effectiveRate: requested,
            nativeRate: candidate,
            compensated: true,
            steppedDown: false,
          };
        }
      } catch {
        // Try the next native bridge rate.
      }
    }
  }

  const candidates = [
    ...VALIDATED_PLAYBACK_RATES.filter((rate) => rate < requested).sort((a, b) => b - a),
  ];

  for (const candidate of candidates) {
    try {
      media.playbackRate = candidate;
      if (media.playbackRate === candidate) {
        return {
          effectiveRate: candidate,
          nativeRate: candidate,
          compensated: false,
          steppedDown: true,
        };
      }
    } catch {
      // Try the next lower validated rate.
    }
  }

  media.playbackRate = 1;
  return {
    effectiveRate: 1,
    nativeRate: 1,
    compensated: false,
    steppedDown: requested !== 1,
  };
}

export function compensatedPlaybackTarget(
  anchorVideoSeconds: number,
  requestedRate: number,
  elapsedMs: number,
  durationSeconds: number,
) {
  const target =
    Math.max(0, anchorVideoSeconds) +
    Math.max(0, requestedRate) * Math.max(0, elapsedMs) / 1_000;
  return Math.min(Math.max(0, durationSeconds), target);
}

export function clampPlaybackTime(seconds: number, durationSeconds: number) {
  if (!Number.isFinite(seconds) || !Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return 0;
  }
  return Math.min(durationSeconds, Math.max(0, seconds));
}

export function coverageGapToleranceMs(playbackRate: number) {
  return Math.max(3_000, Math.ceil(playbackRate * 600));
}
