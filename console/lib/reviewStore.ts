import {
  buildDemoReviewChunks,
  leaseOldestPendingChunk,
  openQueueDepth,
  releaseExpiredLocks,
  tallyClicksToEvents,
  type HumanTallyEvent,
  type ReviewChunk,
  type TallyClick,
} from "@/lib/reviewChunks";
import { demoNowIso } from "@/lib/demoData";

type Store = {
  chunks: ReviewChunk[];
  humanEvents: HumanTallyEvent[];
  sessions: Record<string, { startedAtIso: string; chunksDone: number; clicks: number }>;
  submissions: Record<string, {
    chunkId: string;
    reviewerId: string;
    events: HumanTallyEvent[];
  }>;
};

export type ReviewDayQueueRow = {
  id: string;
  order: number;
  stationName: string;
  timeRange: string;
  state: "working" | "done";
  count: number | null;
  problem: string | null;
};

const globalForReview = globalThis as unknown as { factoryVisionReviewStore?: Store };

function createStore(): Store {
  return {
    chunks: buildDemoReviewChunks(),
    humanEvents: [],
    sessions: {
      "live-session": { startedAtIso: "2026-06-26T14:20:00-07:00", chunksDone: 0, clicks: 0 },
    },
    submissions: {},
  };
}

export function reviewStore() {
  globalForReview.factoryVisionReviewStore ??= createStore();
  return globalForReview.factoryVisionReviewStore;
}

export function resetReviewStoreForTests() {
  globalForReview.factoryVisionReviewStore = createStore();
  return globalForReview.factoryVisionReviewStore;
}

export function getNextChunk(reviewerId: string, now = new Date(demoNowIso)) {
  const store = reviewStore();
  store.sessions[reviewerId] ??= {
    startedAtIso: now.toISOString(),
    chunksDone: 0,
    clicks: 0,
  };

  const existing = store.chunks.find((chunk) => (
    chunk.state === "locked" &&
    chunk.lockedBy === reviewerId &&
    chunk.lockedUntilIso &&
    new Date(chunk.lockedUntilIso).getTime() > now.getTime()
  ));
  const chunk = existing ?? leaseOldestPendingChunk(store.chunks, reviewerId, now);

  return {
    chunk,
  };
}

export function confirmChunk(
  chunkId: string,
  reviewerId: string,
  clicks: TallyClick[],
  idempotencyKey: string,
  problem?: string,
  now = new Date(demoNowIso),
) {
  const store = reviewStore();
  const prior = store.submissions[idempotencyKey];
  if (prior && prior.chunkId === chunkId && prior.reviewerId === reviewerId) {
    const chunk = store.chunks.find((candidate) => candidate.id === chunkId)!;
    return { ok: true as const, chunk, events: prior.events };
  }
  releaseExpiredLocks(store.chunks, now);
  const chunk = store.chunks.find((candidate) => candidate.id === chunkId);

  if (!chunk) {
    return { ok: false as const, status: 404, error: "Chunk not found" };
  }
  if (chunk.state !== "locked" || chunk.lockedBy !== reviewerId) {
    return { ok: false as const, status: 409, error: "Chunk is not locked by this reviewer" };
  }

  const events = problem ? [] : tallyClicksToEvents(chunk, clicks, reviewerId, now);
  store.humanEvents.push(...events);
  chunk.state = "processed";
  chunk.processedBy = reviewerId;
  chunk.processedAtIso = now.toISOString();
  chunk.problem = problem ?? null;
  chunk.lockedBy = null;
  chunk.lockedUntilIso = null;

  const session = (store.sessions[reviewerId] ??= {
    startedAtIso: now.toISOString(),
    chunksDone: 0,
    clicks: 0,
  });
  session.chunksDone += 1;
  session.clicks += events.length;

  store.submissions[idempotencyKey] = { chunkId, reviewerId, events };
  return { ok: true as const, chunk, events };
}

export function getDayQueue(reviewerId: string, now = new Date(demoNowIso)): ReviewDayQueueRow[] {
  const store = reviewStore();
  releaseExpiredLocks(store.chunks, now);
  const counts = new Map<string, number>();
  for (const event of store.humanEvents) {
    counts.set(event.clip_id.split("-tally-")[0], (counts.get(event.clip_id.split("-tally-")[0]) ?? 0) + 1);
  }

  return store.chunks
    .filter((chunk) => (
      (chunk.state === "locked" && chunk.lockedBy === reviewerId) ||
      (chunk.state === "processed" && chunk.processedBy === reviewerId)
    ))
    .map((chunk, index) => ({
      id: chunk.id,
      order: index + 1,
      stationName: chunk.stationName,
      timeRange: `${chunk.startIso.slice(11, 16)}-${chunk.endIso.slice(11, 16)}`,
      state: chunk.state === "processed" ? "done" as const : "working" as const,
      count: chunk.state === "processed" ? counts.get(chunk.id) ?? 0 : null,
      problem: chunk.state === "processed" ? chunk.problem : null,
    }));
}

export function opsSnapshot(now = new Date(demoNowIso)) {
  const store = reviewStore();
  const processed = store.chunks.filter((chunk) => chunk.state === "processed");
  const newestProcessed = processed
    .map((chunk) => new Date(chunk.endIso).getTime())
    .sort((a, b) => b - a)[0];
  const verificationLagMinutes = newestProcessed
    ? Math.round((now.getTime() - newestProcessed) / 60_000)
    : 75;

  return {
    factories: 1,
    camerasUp: 2,
    camerasTotal: 2,
    eventsToday: store.humanEvents.length,
    verificationLagMinutes,
    openQueueDepth: openQueueDepth(store.chunks, now),
    chunksTotal: store.chunks.length,
  };
}
