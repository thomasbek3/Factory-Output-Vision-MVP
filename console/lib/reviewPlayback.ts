export function applyValidatedPlaybackRate(
  media: Pick<HTMLMediaElement, "playbackRate">,
  requested: number,
) {
  try {
    media.playbackRate = requested;
    return { effectiveRate: requested, steppedDown: false };
  } catch {
    media.playbackRate = 1;
    return { effectiveRate: 1, steppedDown: true };
  }
}
