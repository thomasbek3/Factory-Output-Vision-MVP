import { NextRequest } from "next/server";
import { normalizeJobInput, validateNewJobInput } from "@/lib/jobForm";
import { jobSeedFromRecord } from "@/lib/jobRecords";
import { prisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = (await request.json()) as { action?: string } & Record<string, unknown>;

  if (body.action === "edit") {
    const input = normalizeJobInput(body);
    const validation = validateNewJobInput(input);
    if (!validation.ok) {
      return Response.json({ errors: validation.errors }, { status: 400 });
    }
    const record = await prisma.job.update({
      where: { id },
      data: {
        client: input.client.trim(),
        title: input.title.trim(),
        units_required: Math.round(input.units_required),
        quote_usd: Math.round(input.quote_usd),
        cogs_usd: Math.round(input.cogs_usd),
        labor_budget_usd: Math.round(input.labor_budget_usd),
        deadline: new Date(`${input.deadline}T17:30:00-07:00`),
        station_ids: input.station_ids,
      },
    });
    return Response.json({ job: jobSeedFromRecord(record) });
  }

  if (body.action === "pause") {
    const record = await prisma.job.update({
      where: { id },
      data: { status: "paused" },
    });
    return Response.json({ job: jobSeedFromRecord(record) });
  }

  if (body.action === "resume") {
    const record = await prisma.job.update({
      where: { id },
      data: { status: "active", finished_at: null },
    });
    return Response.json({ job: jobSeedFromRecord(record) });
  }

  if (body.action === "finish") {
    const record = await prisma.job.update({
      where: { id },
      data: { status: "finished", finished_at: new Date() },
    });
    return Response.json({ job: jobSeedFromRecord(record) });
  }

  return Response.json({ error: "Unknown action" }, { status: 400 });
}
