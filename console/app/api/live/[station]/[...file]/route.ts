import { createReadStream, statSync } from "node:fs";
import { stat } from "node:fs/promises";
import { Readable } from "node:stream";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma";
import { resolveLivePath } from "@/lib/liveMedia";

// HLS segments are written continuously by the relay; never statically cache.
export const dynamic = "force-dynamic";

/**
 * Serves the live HLS produced by scripts/live-relay.sh from console/live-media.
 * The station allowlist is the set of real Station ids in the DB. Playlists are
 * served no-store (they change every ~2s); .ts segments get a short cache. When
 * no relay is running (factory path down, or CI) the files are absent and we
 * 404 cleanly so the frontend can fall back to the demo loop.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ station: string; file: string[] }> },
) {
  const { station, file } = await params;

  const stationRows = await prisma.station.findMany({ select: { id: true } });
  const allowed = new Set(stationRows.map((row) => row.id));

  const safe = resolveLivePath(station, file, allowed);
  if (!safe) {
    return new Response("Not found", { status: 404 });
  }

  try {
    await stat(safe.absPath);
  } catch {
    // Stream not (yet) live — clean 404 so the tile falls back to demo.
    return new Response("Stream offline", { status: 404 });
  }

  const size = statSync(safe.absPath).size;
  return new Response(
    Readable.toWeb(createReadStream(safe.absPath)) as BodyInit,
    {
      status: 200,
      headers: {
        "Content-Type": safe.contentType,
        "Content-Length": String(size),
        "Cache-Control": safe.cacheControl,
      },
    },
  );
}
