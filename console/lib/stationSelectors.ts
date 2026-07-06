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
    const events = stationEventsThrough(station.id, now);
    const assignedJob = jobForStation(station.id);
    const pace =
      jobSnapshots.find((candidate) => candidate.job.id === assignedJob?.id)?.snapshot ??
      evaluateJobPace(seedJobs[0], 0, now, laborConfig);

    return {
      station,
      events,
      unitsToday: events.length,
      latestEvent: events.at(-1),
      pace,
    };
  });
}
