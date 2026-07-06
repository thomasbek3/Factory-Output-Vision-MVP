import { NextRequest } from "next/server";
import { demoNowIso } from "@/lib/demoData";
import { getNextChunk } from "@/lib/reviewStore";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const reviewerId = params.get("reviewerId") || "live-session";
  const now = new Date(params.get("now") || demoNowIso);
  const payload = getNextChunk(reviewerId, now);

  if (!payload.chunk) {
    return Response.json({ ...payload, message: "No eligible chunks." }, { status: 404 });
  }

  return Response.json(payload);
}
