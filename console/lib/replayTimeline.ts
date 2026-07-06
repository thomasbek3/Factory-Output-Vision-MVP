import { loadDemoCountEvents, type CountEventShape } from "@/lib/demoEvents";

export const REPLAY_WORK_START = 7 * 60;
export const REPLAY_WORK_END = 17 * 60 + 30;
export const REPLAY_CHAPTER_MINUTES = 15;
/** A 15-min window with this many or fewer placements shows individual diamonds. */
export const DIAMOND_CLUSTER_THRESHOLD = 4;

export type ReplayChapter = {
  start: number;
  end: number;
  /** Count of unique verified placement MOMENTS (not unit-expanded events). */
  placementCount: number;
  placements: CountEventShape[];
};

/**
 * Minutes-since-midnight (America/Los_Angeles) for an event timestamp. Kept here
 * so both the component and the unit test compute chapter membership identically.
 */
export function eventMinutesLA(ts: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(ts));
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "0";
  return Number(value("hour")) * 60 + Number(value("minute"));
}

/**
 * Collapse unit-expanded CountEvents to unique placement moments. Each real
 * placement produces N unit rows that share a clip_id; the timeline and chapter
 * counts must reflect the MOMENT (the thing a diamond represents), not the units.
 * This is the fix for the CP7 regression where chapters showed inflated counts
 * (e.g. "51 PLACED") because they counted unit rows.
 */
export function uniquePlacementMoments(events: CountEventShape[]): CountEventShape[] {
  const seen = new Set<string>();
  const out: CountEventShape[] = [];
  for (const event of events) {
    if (seen.has(event.clip_id)) continue;
    seen.add(event.clip_id);
    out.push(event);
  }
  return out;
}

/**
 * Build the 15-minute chapters for a station's (or all) events, counting unique
 * placement moments per window.
 */
export function buildReplayChapters(events: CountEventShape[]): ReplayChapter[] {
  const moments = uniquePlacementMoments(events);
  const chapters: ReplayChapter[] = [];
  const count = (REPLAY_WORK_END - REPLAY_WORK_START) / REPLAY_CHAPTER_MINUTES;
  for (let index = 0; index < count; index += 1) {
    const start = REPLAY_WORK_START + index * REPLAY_CHAPTER_MINUTES;
    const end = start + REPLAY_CHAPTER_MINUTES;
    const placements = moments.filter((event) => {
      const minutes = eventMinutesLA(event.ts);
      return minutes >= start && minutes < end;
    });
    chapters.push({ start, end, placementCount: placements.length, placements });
  }
  return chapters;
}

/** Chapter placement counts for a station id (or "all"), from the demo events. */
export function chapterPlacementCounts(stationId: "all" | string): number[] {
  const all = loadDemoCountEvents();
  const events = stationId === "all" ? all : all.filter((event) => event.station_id === stationId);
  return buildReplayChapters(events).map((chapter) => chapter.placementCount);
}
