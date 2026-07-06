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

export const demoSourceDay = demo.source_day;

function jobIdForRawEvent(event: DemoEventRecord, stationId: string) {
  if (stationId === "gate-line" && event.wall_clock < "12:00:00") {
    return "job-delgado-hvac";
  }
  if (stationId === "gate-line") {
    return "job-alvarez-gates";
  }
  return "job-ramirez-fencing";
}

function unitQuantityForJobEvent(jobId: string, sequence: number) {
  if (jobId === "job-ramirez-fencing") {
    return sequence <= 44 ? 3 : 2;
  }
  if (jobId === "job-delgado-hvac") {
    return sequence <= 10 ? 9 : 8;
  }
  if (jobId === "job-alvarez-gates") {
    return sequence <= 6 ? 2 : 1;
  }
  return 1;
}

export function loadDemoCountEvents(): CountEventShape[] {
  const jobSequences = new Map<string, number>();

  return demo.events.flatMap((event) => {
    const stationId = event.station ?? demo.station;
    const jobId = jobIdForRawEvent(event, stationId);
    const sequence = (jobSequences.get(jobId) ?? 0) + 1;
    jobSequences.set(jobId, sequence);
    const quantity = unitQuantityForJobEvent(jobId, sequence);

    return Array.from({ length: quantity }, (_, unitIndex) => ({
      id: `${event.candidate_id}-u${String(unitIndex + 1).padStart(2, "0")}`,
      station_id: stationId,
      job_id: jobId,
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
    }));
  });
}

export function demoEventSummary() {
  return loadDemoCountEvents().reduce<Record<string, number>>((summary, event) => {
    summary[event.station_id] = (summary[event.station_id] ?? 0) + 1;
    return summary;
  }, {});
}
