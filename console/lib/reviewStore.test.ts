import { beforeEach, describe, expect, it } from "vitest";
import {
  confirmChunk,
  getDayQueue,
  getNextChunk,
  resetReviewStoreForTests,
} from "@/lib/reviewStore";

const now = new Date("2026-06-26T14:32:00-07:00");

describe("review store confirmation", () => {
  beforeEach(() => {
    resetReviewStoreForTests();
  });

  it("returns the original result when an idempotency key is retried", () => {
    const chunk = getNextChunk("reviewer-1", now).chunk!;
    const clicks = [{ id: "stable-click", videoSec: 12 }];

    const first = confirmChunk(chunk.id, "reviewer-1", clicks, "submission-1", undefined, now);
    const retry = confirmChunk(chunk.id, "reviewer-1", clicks, "submission-1", undefined, now);

    expect(first.ok).toBe(true);
    expect(retry).toEqual(first);
    expect(getDayQueue("reviewer-1", now).find((row) => row.id === chunk.id)).toMatchObject({
      state: "done",
      count: 1,
    });
  });

  it("processes a problem chunk with no events and preserves the reason", () => {
    const chunk = getNextChunk("reviewer-1", now).chunk!;

    const result = confirmChunk(chunk.id, "reviewer-1", [], "problem-1", "camera-blocked", now);

    expect(result).toMatchObject({ ok: true, events: [] });
    expect(getDayQueue("reviewer-1", now).find((row) => row.id === chunk.id)).toMatchObject({
      state: "done",
      count: 0,
      problem: "camera-blocked",
    });
  });
});

describe("review day queue", () => {
  beforeEach(() => {
    resetReviewStoreForTests();
  });

  it("projects only the caller's own leased or completed work", () => {
    const current = getNextChunk("reviewer-1", now).chunk!;
    const peer = getNextChunk("reviewer-2", now).chunk!;

    const queue = getDayQueue("reviewer-1", now);

    expect(queue).toHaveLength(1);
    expect(queue.map((row) => row.order)).toEqual([1]);
    expect(queue.find((row) => row.id === current.id)?.state).toBe("working");
    expect(queue.some((row) => row.id === peer.id)).toBe(false);
    expect(queue[0]).toMatchObject({
      stationName: "Gate line",
      timeRange: "07:00-07:15",
    });
  });
});
