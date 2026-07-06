import type { JobSeed } from "@/lib/demoData";

/**
 * Guard for owner-facing surfaces (Jobs, History): test/probe/smoke rows that
 * exist for internal verification must never appear to the factory owner. We
 * match on client OR title so a "CP3 Smoke" client and a "probe" title are both
 * excluded. Ops (internal) surfaces are exempt — they call the DB directly.
 */
const HIDDEN_TITLE_RE = /probe|smoke/i;

export function isOwnerVisibleJob(job: Pick<JobSeed, "client" | "title">) {
  return !HIDDEN_TITLE_RE.test(job.client) && !HIDDEN_TITLE_RE.test(job.title);
}

export function ownerVisibleJobs<T extends Pick<JobSeed, "client" | "title">>(jobs: T[]): T[] {
  return jobs.filter(isOwnerVisibleJob);
}
