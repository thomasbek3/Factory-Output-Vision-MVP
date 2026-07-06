import { NextRequest } from "next/server";
import { jobs as seedJobs } from "@/lib/demoData";
import { validateNewJobInput, type NewJobInput } from "@/lib/jobForm";
import { jobSeedFromRecord } from "@/lib/jobRecords";
import { prisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";

function parseNumber(value: unknown) {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  return Number.NaN;
}

function normalizeInput(body: Record<string, unknown>): NewJobInput {
  return {
    client: String(body.client ?? ""),
    title: String(body.title ?? ""),
    units_required: parseNumber(body.units_required),
    quote_usd: parseNumber(body.quote_usd),
    cogs_usd: parseNumber(body.cogs_usd),
    labor_budget_usd: parseNumber(body.labor_budget_usd),
    deadline: String(body.deadline ?? ""),
    station_ids: Array.isArray(body.station_ids) ? body.station_ids.map(String) : [],
  };
}

export async function GET() {
  try {
    const records = await prisma.job.findMany({
      orderBy: [{ status: "asc" }, { created_at: "asc" }],
    });
    return Response.json({ jobs: records.map(jobSeedFromRecord) });
  } catch (error) {
    // Fall back to seed data so the page never hard-crashes, but LOG the failure:
    // a silent catch here previously masked a native-module ABI mismatch that made
    // every DB write 500 while reads looked healthy.
    console.error("GET /api/jobs failed, serving seed jobs:", error);
    return Response.json({ jobs: seedJobs });
  }
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Record<string, unknown>;
  const input = normalizeInput(body);
  const validation = validateNewJobInput(input);

  if (!validation.ok) {
    return Response.json({ errors: validation.errors }, { status: 400 });
  }

  const record = await prisma.job.create({
    data: {
      id: `job-${crypto.randomUUID()}`,
      client: input.client.trim(),
      title: input.title.trim(),
      units_required: Math.round(input.units_required),
      quote_usd: Math.round(input.quote_usd),
      cogs_usd: Math.round(input.cogs_usd),
      labor_budget_usd: Math.round(input.labor_budget_usd),
      deadline: new Date(`${input.deadline}T17:30:00-07:00`),
      station_ids: input.station_ids,
      status: "active",
      created_at: new Date(),
      finished_at: null,
    },
  });

  return Response.json({ job: jobSeedFromRecord(record) }, { status: 201 });
}
