import { NextRequest } from "next/server";
import { findEventByClipId } from "@/lib/demoData";
import { prisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const clips = await prisma.savedClip.findMany({
      orderBy: { savedAt: "desc" },
      take: 50,
    });
    return Response.json({
      clips: clips.map((clip) => ({
        id: clip.id,
        eventId: clip.eventId,
        stationId: clip.stationId,
        ts: clip.ts.toISOString(),
        note: clip.note,
        savedAt: clip.savedAt.toISOString(),
      })),
    });
  } catch (error) {
    console.error("GET /api/clips failed:", error);
    return Response.json({ clips: [] });
  }
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { eventId?: string; note?: string };
  const eventId = typeof body.eventId === "string" ? body.eventId : "";
  const event = findEventByClipId(eventId);
  if (!event) {
    return Response.json({ error: "Unknown event" }, { status: 400 });
  }

  const clip = await prisma.savedClip.create({
    data: {
      eventId,
      stationId: event.station_id,
      ts: new Date(event.ts),
      note: typeof body.note === "string" && body.note.trim() ? body.note.trim() : null,
    },
  });

  return Response.json(
    {
      clip: {
        id: clip.id,
        eventId: clip.eventId,
        stationId: clip.stationId,
        ts: clip.ts.toISOString(),
        note: clip.note,
        savedAt: clip.savedAt.toISOString(),
      },
    },
    { status: 201 },
  );
}
