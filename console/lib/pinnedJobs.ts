import { jobs as seedJobs, type JobSeed } from "@/lib/demoData";

/**
 * The three pinned demo jobs ARE the demo-day narrative: they drive the +$532
 * money strip and the "Alvarez Gates is losing money" sentence. Their canonical
 * state lives in the seed, not the mutable dev.db. A stale DB (jobs left
 * "finished" by a prior finish action or a CP9 reset) must not collapse the
 * pinned story to "+$0 · All 0 jobs on pace" while the camera/KPI scoreboards
 * still tell the demo story off the pinned event log.
 *
 * So we always render these IDs from the seed and let the DB own only genuinely
 * new jobs. This keeps the money strip, jobs list, and pace math on the same
 * demo-clock narrative until real counting replaces the seed.
 */
const seedById = new Map(seedJobs.map((job) => [job.id, job]));

export function pinDemoNarrative(dbJobs: JobSeed[]): JobSeed[] {
  const seen = new Set<string>();
  const reconciled = dbJobs.map((job) => {
    seen.add(job.id);
    return seedById.get(job.id) ?? job;
  });
  // Include any pinned demo job the DB dropped entirely.
  for (const seed of seedJobs) {
    if (!seen.has(seed.id)) reconciled.push(seed);
  }
  return reconciled;
}
