import { NextRequest } from "next/server";
import { demoNowIso } from "@/lib/demoData";
import { confirmChunk } from "@/lib/reviewStore";
import type { TallyClick } from "@/lib/reviewChunks";

export const dynamic = "force-dynamic";

function normalizeClicks(value: unknown): TallyClick[] {
  if (!Array.isArray(value)) return [];
  return value.map((click, index) => {
    const record = click as Partial<TallyClick>;
    return {
      id: String(record.id ?? `click-${index + 1}`),
      videoSec: Number(record.videoSec ?? 0),
    };
  });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = (await request.json()) as Record<string, unknown>;
  const reviewerId = String(body.reviewerId || "live-session");
  const now = new Date(String(body.now || demoNowIso));
  const result = confirmChunk(id, reviewerId, normalizeClicks(body.clicks), now);

  if (!result.ok) {
    return Response.json({ error: result.error }, { status: result.status });
  }

  return Response.json({
    chunk: result.chunk,
    events: result.events,
    stats: result.stats,
  });
}
