import type { Job } from "@prisma/client";
import type { JobSeed } from "@/lib/demoData";

export function jobSeedFromRecord(job: Job): JobSeed {
  return {
    id: job.id,
    client: job.client,
    title: job.title,
    units_required: job.units_required,
    quote_usd: job.quote_usd,
    cogs_usd: job.cogs_usd,
    labor_budget_usd: job.labor_budget_usd,
    deadline: job.deadline.toISOString(),
    station_ids: Array.isArray(job.station_ids) ? job.station_ids.map(String) : [],
    status: job.status,
    created_at: job.created_at.toISOString(),
  };
}
