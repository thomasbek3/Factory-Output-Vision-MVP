#!/usr/bin/env node
/**
 * Derive a plausible 2026-06-25 demo events file from the real 2026-06-26 capture.
 *
 * This is NOT a raw pipeline capture — it is a deterministic, clearly-labelled
 * synthesis so the Replay "Tapes" archive has a genuinely different second day
 * (different chapter counts, shifted times). The Jun 25 FOOTAGE is real (cut by
 * prepare-demo-media.sh from factory-live-20260625); only the per-placement
 * event list is derived, because we never ran the counter on that day.
 *
 * Rules (deterministic):
 *   - drop every 3rd pallet-a event and every 4th gate-line event (lighter day)
 *   - shift each remaining event 8–11.5 min later (crew started later, ran tighter)
 *   - tag candidate ids with an x25 marker so nothing collides with Jun 26 clips
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const demoDir = join(here, "..", "demo");

const src = JSON.parse(readFileSync(join(demoDir, "demo_events.json"), "utf8"));

function toSec(wall) {
  const [h, m, s] = wall.split(":").map(Number);
  return h * 3600 + m * 60 + s;
}
function toWall(sec) {
  const clamped = Math.max(0, sec);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = clamped % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

let index = 0;
const events = [];
for (const event of src.events) {
  index += 1;
  const station = event.station ?? src.station;
  if (station === "pallet-a" && index % 3 === 0) continue;
  if (station === "gate-line" && index % 4 === 0) continue;
  const shift = 480 + ((index * 37) % 210);
  events.push({
    station,
    wall_clock: toWall(toSec(event.wall_clock) + shift),
    offset_sec: event.offset_sec,
    candidate_id: event.candidate_id.replace(/^(pa|gl)-/, "$1x25-"),
    confidence: Math.round((event.confidence * 0.98 + 0.01) * 100) / 100,
  });
}
events.sort((a, b) => a.wall_clock.localeCompare(b.wall_clock));

const out = {
  schema: "demo-events-v1",
  header:
    "DERIVED demo day — synthesized from demo_events.json by scripts/derive-jun25-events.mjs; NOT a raw pipeline capture.",
  derived_from: "demo_events.json (2026-06-26)",
  station: "pallet-a",
  source_day: "2026-06-25",
  clip_start_wall: events[0].wall_clock,
  events,
};

writeFileSync(join(demoDir, "demo_events_20260625.json"), `${JSON.stringify(out, null, 2)}\n`);
const pa = events.filter((e) => e.station === "pallet-a").length;
const gl = events.filter((e) => e.station === "gate-line").length;
console.log(`wrote ${events.length} events (pallet-a ${pa}, gate-line ${gl})`);
