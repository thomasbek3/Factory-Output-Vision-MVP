import {
  jobForStation,
  laborConfig,
  stationEventsThrough,
  stations,
  jobs as seedJobs,
  type JobSeed,
  type StationSeed,
} from "@/lib/demoData";
import { evaluateJobPace, type PaceSnapshot } from "@/lib/paceMath";
import { selectRunningJobSnapshots } from "@/lib/jobSelectors";

const ownerStationStories: Record<string, { unitsToday: number; paceDelta: number }> = {
  "pallet-a": { unitsToday: 142, paceDelta: 18 },
  "gate-line": { unitsToday: 58, paceDelta: -21 },
};

export type StationCountSnapshot = {
  station: StationSeed;
  events: ReturnType<typeof stationEventsThrough>;
  unitsToday: number;
  latestEvent: ReturnType<typeof stationEventsThrough>[number] | undefined;
  pace: PaceSnapshot;
};

export function selectStationCountSnapshots(
  now: Date,
  sourceJobs: JobSeed[] = seedJobs,
): StationCountSnapshot[] {
  const jobSnapshots = selectRunningJobSnapshots(now, sourceJobs);

  return stations.map((station) => {
    const rawEvents = stationEventsThrough(station.id, now);
    const assignedJob = jobForStation(station.id);
    const rawPace =
      jobSnapshots.find((candidate) => candidate.job.id === assignedJob?.id)?.snapshot ??
      evaluateJobPace(seedJobs[0], 0, now, laborConfig);
    const story = ownerStationStories[station.id];
    const events = story ? rawEvents.slice(-story.unitsToday) : rawEvents;
    const pace = story
      ? {
          ...rawPace,
          expected_units_by_now: story.unitsToday - story.paceDelta,
          pace_delta: story.paceDelta,
          units_done: story.unitsToday,
        }
      : rawPace;

    return {
      station,
      events,
      unitsToday: story?.unitsToday ?? rawEvents.length,
      latestEvent: events.at(-1),
      pace,
    };
  });
}
