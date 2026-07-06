import { describe, expect, it } from "vitest";
import {
  buildDemoReviewChunks,
  eligiblePendingChunks,
  leaseOldestPendingChunk,
  releaseExpiredLocks,
  tallyClicksToEvents,
  wallClockForClick,
} from "@/lib/reviewChunks";

describe("review chunker", () => {
  it("splits the demo day into 15-minute chunks per station", () => {
    const chunks = buildDemoReviewChunks();

    expect(chunks).toHaveLength(84);
    expect(chunks[0]).toMatchObject({
      id: "gate-line-0700",
      stationId: "gate-line",
      startIso: "2026-06-26T07:00:00-07:00",
      endIso: "2026-06-26T07:15:00-07:00",
    });
    expect(chunks.at(-1)).toMatchObject({
      id: "pallet-a-1715",
      stationId: "pallet-a",
      startIso: "2026-06-26T17:15:00-07:00",
      endIso: "2026-06-26T17:30:00-07:00",
    });
    expect(chunks.find((chunk) => chunk.isGolden)).toMatchObject({
      id: "pallet-a-1345",
      goldenCount: 6,
    });
  });

  it("serves only pending chunks at least 60 minutes behind now", () => {
    const chunks = buildDemoReviewChunks();
    const eligible = eligiblePendingChunks(chunks, new Date("2026-06-26T14:32:00-07:00"));

    expect(eligible).toHaveLength(52);
    expect(eligible[0].id).toBe("gate-line-0700");
    expect(eligible.at(-1)?.endIso).toBe("2026-06-26T13:30:00-07:00");
  });
});

describe("review chunk leases", () => {
  it("locks the oldest eligible chunk and releases it after timeout", () => {
    const chunks = buildDemoReviewChunks();
    const locked = leaseOldestPendingChunk(chunks, "reviewer-1", new Date("2026-06-26T14:32:00-07:00"));

    expect(locked?.id).toBe("gate-line-0700");
    expect(locked?.state).toBe("locked");
    expect(locked?.lockedBy).toBe("reviewer-1");

    releaseExpiredLocks(chunks, new Date("2026-06-26T14:36:59-07:00"));
    expect(locked?.state).toBe("locked");

    releaseExpiredLocks(chunks, new Date("2026-06-26T14:37:00-07:00"));
    expect(locked?.state).toBe("pending");
    expect(locked?.lockedBy).toBeNull();
  });
});

describe("tally event mapping", () => {
  it("maps click video seconds to human CountEvent-shaped records", () => {
    const chunk = buildDemoReviewChunks()[0];
    const clicks = [
      { id: "a", videoSec: 12 },
      { id: "b", videoSec: 61.5 },
      { id: "c", videoSec: 120 },
    ];
    const events = tallyClicksToEvents(chunk, clicks, "reviewer-1", new Date("2026-06-26T14:32:00-07:00"));

    expect(events).toHaveLength(3);
    expect(events.map((event) => event.source)).toEqual(["human_tally", "human_tally", "human_tally"]);
    expect(events[0]).toMatchObject({
      station_id: "gate-line",
      ts: "2026-06-26T14:00:12.000Z",
      verdict: "placed",
      verified_by: "reviewer-1",
    });
    expect(wallClockForClick(chunk, 9999)).toBe("2026-06-26T14:15:00.000Z");
  });
});
