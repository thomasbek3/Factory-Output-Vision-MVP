import demoEvents from "@/demo/demo_events.json";

export type DemoEventRecord = {
  wall_clock: string;
  offset_sec: number;
  candidate_id: string;
  confidence: number;
  station?: string;
};

export type CountEventShape = {
  id: string;
  station_id: string;
  job_id: string | null;
  ts: string;
  clip_id: string;
  source: "tripwire";
  verdict: "placed";
  verified_by: "demo-seed";
  verified_at: string;
  demo_offset_sec: number;
  model_verdict: {
    verdict: "placed";
    confidence: number;
  };
  disputed: false;
};

type DemoEventsFile = {
  schema: "demo-events-v1";
  header: string;
  station: string;
  source_day: string;
  clip_start_wall: string;
  events: DemoEventRecord[];
};

const demo = demoEvents as DemoEventsFile;

export function loadDemoCountEvents(): CountEventShape[] {
  return demo.events.map((event) => {
    const stationId = event.station ?? demo.station;

    return {
      id: event.candidate_id,
      station_id: stationId,
      job_id: stationId === "gate-line" ? "job-alvarez-gates" : "job-ramirez-fencing",
      ts: `${demo.source_day}T${event.wall_clock}-07:00`,
      clip_id: `clip-${event.candidate_id}`,
      source: "tripwire",
      verdict: "placed",
      verified_by: "demo-seed",
      verified_at: `${demo.source_day}T${event.wall_clock}-07:00`,
      demo_offset_sec: event.offset_sec,
      model_verdict: {
        verdict: "placed",
        confidence: event.confidence,
      },
      disputed: false,
    };
  });
}

export function demoEventSummary() {
  return loadDemoCountEvents().reduce<Record<string, number>>((summary, event) => {
    summary[event.station_id] = (summary[event.station_id] ?? 0) + 1;
    return summary;
  }, {});
}
