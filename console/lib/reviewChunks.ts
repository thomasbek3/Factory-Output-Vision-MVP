import { demoDay, jobs, mediaBucketForTime, mediaUrlForStation, stations } from "@/lib/demoData";

export type ReviewChunkState = "pending" | "locked" | "processed";

export type TallyClick = {
  id: string;
  videoSec: number;
};

export type ReviewChunk = {
  id: string;
  stationId: string;
  stationName: string;
  startIso: string;
  endIso: string;
  mediaUrl: string;
  posterUrl: string;
  state: ReviewChunkState;
  lockedBy: string | null;
  lockedUntilIso: string | null;
  processedBy: string | null;
  processedAtIso: string | null;
  problem: string | null;
  isGolden: boolean;
  goldenCount: number | null;
};

export type HumanTallyEvent = {
  id: string;
  station_id: string;
  job_id: string | null;
  ts: string;
  clip_id: string;
  source: "human_tally";
  verdict: "placed";
  verified_by: string;
  verified_at: string;
  video_sec: number;
};

export const chunkMinutes = 15;
export const defaultReviewDelayMinutes = 60;
export const defaultLeaseMinutes = 5;
export const reviewerStations = ["pallet-a", "gate-line"];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function isoAt(minutesAfterStart: number) {
  const hour = 7 + Math.floor(minutesAfterStart / 60);
  const minute = minutesAfterStart % 60;
  return `${demoDay}T${pad(hour)}:${pad(minute)}:00-07:00`;
}

function formatIdTime(iso: string) {
  return iso.slice(11, 16).replace(":", "");
}

export function buildDemoReviewChunks() {
  const chunks: ReviewChunk[] = [];
  const workMinutes = 10.5 * 60;

  for (const station of stations) {
    for (let minute = 0; minute < workMinutes; minute += chunkMinutes) {
      const startIso = isoAt(minute);
      const endIso = isoAt(minute + chunkMinutes);
      const start = new Date(startIso);
      const bucket = mediaBucketForTime(start);
      const isGolden = station.id === "pallet-a" && startIso.endsWith("13:45:00-07:00");

      chunks.push({
        id: `${station.id}-${formatIdTime(startIso)}`,
        stationId: station.id,
        stationName: station.name,
        startIso,
        endIso,
        mediaUrl: mediaUrlForStation(station.id, start),
        posterUrl: `/api/media/${station.mediaSlug}/${bucket}.jpg`,
        state: "pending",
        lockedBy: null,
        lockedUntilIso: null,
        processedBy: null,
        processedAtIso: null,
        problem: null,
        isGolden,
        goldenCount: isGolden ? 6 : null,
      });
    }
  }

  return chunks.sort((a, b) => {
    const timeDelta = new Date(a.startIso).getTime() - new Date(b.startIso).getTime();
    return timeDelta || a.stationId.localeCompare(b.stationId);
  });
}

export function eligiblePendingChunks(
  chunks: ReviewChunk[],
  now: Date,
  stationIds = reviewerStations,
  delayMinutes = defaultReviewDelayMinutes,
) {
  const cutoff = now.getTime() - delayMinutes * 60_000;
  return chunks.filter((chunk) => (
    stationIds.includes(chunk.stationId) &&
    chunk.state === "pending" &&
    new Date(chunk.endIso).getTime() <= cutoff
  ));
}

export function releaseExpiredLocks(chunks: ReviewChunk[], now: Date) {
  for (const chunk of chunks) {
    if (
      chunk.state === "locked" &&
      chunk.lockedUntilIso &&
      new Date(chunk.lockedUntilIso).getTime() <= now.getTime()
    ) {
      chunk.state = "pending";
      chunk.lockedBy = null;
      chunk.lockedUntilIso = null;
    }
  }
}

export function leaseOldestPendingChunk(
  chunks: ReviewChunk[],
  reviewerId: string,
  now: Date,
  stationIds = reviewerStations,
  leaseMinutes = defaultLeaseMinutes,
) {
  releaseExpiredLocks(chunks, now);
  const chunk = eligiblePendingChunks(chunks, now, stationIds)[0];
  if (!chunk) return null;

  chunk.state = "locked";
  chunk.lockedBy = reviewerId;
  chunk.lockedUntilIso = new Date(now.getTime() + leaseMinutes * 60_000).toISOString();
  return chunk;
}

export function wallClockForClick(chunk: ReviewChunk, videoSec: number) {
  const boundedSec = Math.max(0, Math.min(chunkMinutes * 60, videoSec));
  return new Date(new Date(chunk.startIso).getTime() + boundedSec * 1000).toISOString();
}

function jobIdForChunk(chunk: ReviewChunk) {
  return jobs.find((job) => job.station_ids.includes(chunk.stationId) && job.status === "active")?.id ?? null;
}

export function tallyClicksToEvents(
  chunk: ReviewChunk,
  clicks: TallyClick[],
  reviewerId: string,
  verifiedAt: Date,
): HumanTallyEvent[] {
  return clicks.map((click, index) => ({
    id: `${chunk.id}-human-${String(index + 1).padStart(2, "0")}`,
    station_id: chunk.stationId,
    job_id: jobIdForChunk(chunk),
    ts: wallClockForClick(chunk, click.videoSec),
    clip_id: `${chunk.id}-tally-${String(index + 1).padStart(2, "0")}`,
    source: "human_tally",
    verdict: "placed",
    verified_by: reviewerId,
    verified_at: verifiedAt.toISOString(),
    video_sec: click.videoSec,
  }));
}

export function openQueueDepth(chunks: ReviewChunk[], now: Date) {
  releaseExpiredLocks(chunks, now);
  return eligiblePendingChunks(chunks, now).length;
}
