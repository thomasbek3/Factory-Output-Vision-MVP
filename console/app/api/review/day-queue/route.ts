import { NextRequest } from "next/server";
import { demoNowIso } from "@/lib/demoData";
import { getDayQueue } from "@/lib/reviewStore";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const reviewerId = params.get("reviewerId") || "live-session";
  const now = new Date(params.get("now") || demoNowIso);

  return Response.json({ chunks: getDayQueue(reviewerId, now) });
}
