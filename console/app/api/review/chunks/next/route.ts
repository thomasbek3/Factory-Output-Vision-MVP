import { NextRequest } from "next/server";
import { demoNowIso } from "@/lib/demoData";
import { getNextChunk } from "@/lib/reviewStore";
import type { ReviewChunk } from "@/lib/reviewChunks";

export const dynamic = "force-dynamic";

function workerChunk(chunk: ReviewChunk | null) {
  if (!chunk) return null;
  return {
    id: chunk.id,
    stationId: chunk.stationId,
    stationName: chunk.stationName,
    startIso: chunk.startIso,
    endIso: chunk.endIso,
    mediaUrl: chunk.mediaUrl,
    posterUrl: chunk.posterUrl,
    state: chunk.state,
    lockedUntilIso: chunk.lockedUntilIso,
    processedAtIso: chunk.processedAtIso,
    problem: chunk.problem,
  };
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const reviewerId = params.get("reviewerId") || "live-session";
  const now = new Date(params.get("now") || demoNowIso);
  const payload = getNextChunk(reviewerId, now);

  if (!payload.chunk) {
    return Response.json({ ...payload, message: "No eligible chunks." }, { status: 404 });
  }

  return Response.json({
    chunk: workerChunk(payload.chunk),
    nextChunk: workerChunk(payload.nextChunk),
  });
}
