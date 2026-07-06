import { describe, expect, it } from "vitest";
import {
  DIAMOND_CLUSTER_THRESHOLD,
  REPLAY_CHAPTER_MINUTES,
  REPLAY_WORK_END,
  REPLAY_WORK_START,
  buildReplayChapters,
  chapterPlacementCounts,
  uniquePlacementMoments,
} from "@/lib/replayTimeline";
import { loadDemoCountEvents } from "@/lib/demoEvents";

function chapterAt(counts: number[], hour: number, minute: number) {
  const index = (hour * 60 + minute - REPLAY_WORK_START) / REPLAY_CHAPTER_MINUTES;
  return counts[index];
}

describe("replay chapter counts", () => {
  it("counts unique placement moments, not unit-expanded rows", () => {
    // Regression guard: pallet-a events unit-expand to hundreds of rows, but the
    // chapters must reflect placement MOMENTS. If this counted unit rows we'd see
    // values like 15/21/51 instead of the real 4–9 per window.
    const counts = chapterPlacementCounts("pallet-a");
    const max = Math.max(...counts);
    expect(max).toBeLessThan(15); // unit-inflated counts were >=15
    // Pinned real windows (derived from demo/demo_events.json):
    expect(chapterAt(counts, 12, 0)).toBe(7);
    expect(chapterAt(counts, 13, 45)).toBe(6);
    expect(chapterAt(counts, 10, 15)).toBe(5);
  });

  it("has at least one chapter with exactly 6 placements (acceptance)", () => {
    const counts = chapterPlacementCounts("pallet-a");
    expect(counts.filter((n) => n === 6).length).toBeGreaterThanOrEqual(1);
  });

  it("marks genuinely empty windows as zero", () => {
    const counts = chapterPlacementCounts("pallet-a");
    // Before the first event (10:15) the early windows are truly quiet.
    expect(chapterAt(counts, 7, 0)).toBe(0);
    expect(chapterAt(counts, 9, 0)).toBe(0);
  });

  it("gate-line has sparse windows that stay individual (<= cluster threshold)", () => {
    const counts = chapterPlacementCounts("gate-line");
    const nonZero = counts.filter((n) => n > 0);
    expect(nonZero.length).toBeGreaterThan(0);
    // Sparse windows (1–3 placements) exist and are at/under the cluster threshold.
    expect(nonZero.some((n) => n <= DIAMOND_CLUSTER_THRESHOLD)).toBe(true);
  });

  it("uniquePlacementMoments dedupes by clip_id", () => {
    const events = loadDemoCountEvents().filter((event) => event.station_id === "pallet-a");
    const moments = uniquePlacementMoments(events);
    expect(moments.length).toBeLessThan(events.length);
    expect(new Set(moments.map((event) => event.clip_id)).size).toBe(moments.length);
  });

  it("chapters cover the full work day", () => {
    const chapters = buildReplayChapters(loadDemoCountEvents());
    expect(chapters[0].start).toBe(REPLAY_WORK_START);
    expect(chapters.at(-1)?.end).toBe(REPLAY_WORK_END);
  });
});
