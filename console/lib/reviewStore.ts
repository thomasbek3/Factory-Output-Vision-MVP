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

export type ReviewerMetric = {
  reviewerId: string;
  name: string;
  chunksToday: number;
  clicksToday: number;
  chunksPerHour: number;
  goldenAccuracyPct: number | null;
};

type Store = {
  chunks: ReviewChunk[];
  humanEvents: HumanTallyEvent[];
  sessions: Record<string, { name: string; startedAtIso: string; chunksDone: number; clicks: number }>;
  golden: Record<string, { correct: number; total: number }>;
};

const globalForReview = globalThis as unknown as { factoryVisionReviewStore?: Store };

function createStore(): Store {
  return {
    chunks: buildDemoReviewChunks(),
    humanEvents: [],
    sessions: {
      "m-reyes": { name: "M. Reyes", startedAtIso: "2026-06-26T12:00:00-07:00", chunksDone: 12, clicks: 74 },
      "a-kim": { name: "A. Kim", startedAtIso: "2026-06-26T12:30:00-07:00", chunksDone: 9, clicks: 52 },
      "live-session": { name: "Live session", startedAtIso: "2026-06-26T14:20:00-07:00", chunksDone: 0, clicks: 0 },
    },
    golden: {
      "m-reyes": { correct: 23, total: 24 },
      "a-kim": { correct: 19, total: 20 },
    },
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
    name: reviewerId === "live-session" ? "Live session" : reviewerId,
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
  const next = store.chunks.find((candidate) => (
    candidate.state === "pending" &&
    candidate.id !== chunk?.id &&
    new Date(candidate.endIso).getTime() <= now.getTime() - 60 * 60_000
  )) ?? null;

  return {
    chunk,
    nextChunk: next,
    stats: sessionStats(reviewerId, now),
    queueDepth: openQueueDepth(store.chunks, now),
  };
}

export function confirmChunk(
  chunkId: string,
  reviewerId: string,
  clicks: TallyClick[],
  now = new Date(demoNowIso),
) {
  const store = reviewStore();
  releaseExpiredLocks(store.chunks, now);
  const chunk = store.chunks.find((candidate) => candidate.id === chunkId);

  if (!chunk) {
    return { ok: false as const, status: 404, error: "Chunk not found" };
  }
  if (chunk.state !== "locked" || chunk.lockedBy !== reviewerId) {
    return { ok: false as const, status: 409, error: "Chunk is not locked by this reviewer" };
  }

  const events = tallyClicksToEvents(chunk, clicks, reviewerId, now);
  store.humanEvents.push(...events);
  chunk.state = "processed";
  chunk.processedBy = reviewerId;
  chunk.processedAtIso = now.toISOString();
  chunk.lockedBy = null;
  chunk.lockedUntilIso = null;

  const session = (store.sessions[reviewerId] ??= {
    name: reviewerId,
    startedAtIso: now.toISOString(),
    chunksDone: 0,
    clicks: 0,
  });
  session.chunksDone += 1;
  session.clicks += clicks.length;

  if (chunk.isGolden && chunk.goldenCount !== null) {
    const accuracy = (store.golden[reviewerId] ??= { correct: 0, total: 0 });
    accuracy.total += 1;
    if (clicks.length === chunk.goldenCount) accuracy.correct += 1;
  }

  return { ok: true as const, chunk, events, stats: sessionStats(reviewerId, now) };
}

export function sessionStats(reviewerId: string, now = new Date(demoNowIso)) {
  const store = reviewStore();
  const session = store.sessions[reviewerId] ?? {
    name: reviewerId,
    startedAtIso: now.toISOString(),
    chunksDone: 0,
    clicks: 0,
  };
  const hours = Math.max((now.getTime() - new Date(session.startedAtIso).getTime()) / 3_600_000, 0.25);
  return {
    chunksDone: session.chunksDone,
    clicks: session.clicks,
    chunksPerHour: Number((session.chunksDone / hours).toFixed(1)),
  };
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
    humanEvents: store.humanEvents,
    reviewers: reviewerMetrics(now),
  };
}

export function reviewerMetrics(now = new Date(demoNowIso)): ReviewerMetric[] {
  const store = reviewStore();
  return Object.entries(store.sessions).map(([reviewerId, session]) => {
    const golden = store.golden[reviewerId];
    const hours = Math.max((now.getTime() - new Date(session.startedAtIso).getTime()) / 3_600_000, 0.25);
    return {
      reviewerId,
      name: session.name,
      chunksToday: session.chunksDone,
      clicksToday: session.clicks,
      chunksPerHour: Number((session.chunksDone / hours).toFixed(1)),
      goldenAccuracyPct: golden && golden.total > 0 ? Math.round((golden.correct / golden.total) * 100) : null,
    };
  });
}
