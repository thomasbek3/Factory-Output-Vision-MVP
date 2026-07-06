import { NextRequest } from "next/server";
import { jobSeedFromRecord } from "@/lib/jobRecords";
import { prisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = (await request.json()) as { action?: string };

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
