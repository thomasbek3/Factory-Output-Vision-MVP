export type ReviewTimeline = {
  canonicalStartMs: number;
  canonicalEndMs: number;
  renditionStartMs: number;
  renditionEndMs: number;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function videoTimeToSourceMs(
  videoTimeSec: number,
  videoDurationSec: number,
  timeline: ReviewTimeline,
) {
  const renditionSpan = timeline.renditionEndMs - timeline.renditionStartMs;
  if (videoDurationSec <= 0 || renditionSpan <= 0) return timeline.renditionStartMs;
  const progress = clamp(videoTimeSec / videoDurationSec, 0, 1);
  return Math.round(timeline.renditionStartMs + progress * renditionSpan);
}

export function sourceTimeToVideoSec(
  sourceTimeMs: number,
  videoDurationSec: number,
  timeline: ReviewTimeline,
) {
  const renditionSpan = timeline.renditionEndMs - timeline.renditionStartMs;
  if (videoDurationSec <= 0 || renditionSpan <= 0) return 0;
  const progress = clamp(
    (sourceTimeMs - timeline.renditionStartMs) / renditionSpan,
    0,
    1,
  );
  return progress * videoDurationSec;
}

export function isCountableSourceTime(
  sourceTimeMs: number,
  timeline: ReviewTimeline,
) {
  return (
    sourceTimeMs >= timeline.canonicalStartMs &&
    sourceTimeMs < timeline.canonicalEndMs
  );
}

export function timelineDurationMatches(
  videoDurationSec: number,
  timeline: ReviewTimeline,
) {
  if (!Number.isFinite(videoDurationSec) || videoDurationSec <= 0) return false;
  const renditionSpanMs = timeline.renditionEndMs - timeline.renditionStartMs;
  if (renditionSpanMs <= 0) return false;
  const toleranceMs = Math.max(2_000, renditionSpanMs * 0.005);
  return Math.abs(videoDurationSec * 1_000 - renditionSpanMs) <= toleranceMs;
}
