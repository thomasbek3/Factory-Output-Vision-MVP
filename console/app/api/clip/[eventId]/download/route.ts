import { spawn } from "node:child_process";
import { createReadStream, statSync } from "node:fs";
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { Readable } from "node:stream";
import { NextRequest } from "next/server";
import { findEventByClipId, mediaBucketForTime, stations } from "@/lib/demoData";

export const dynamic = "force-dynamic";

const FFMPEG = process.env.FFMPEG ?? "/opt/homebrew/bin/ffmpeg";
const cacheRoot = path.join(process.cwd(), "tmp", "clips");
const demoMediaRoot = path.join(process.cwd(), "demo-media");
const CLIP_PAD_SEC = 5;

/** Only clip/event ids we mint: clip-<alnum-.-_>. Rejects traversal + shell metachars. */
function sanitizeEventId(raw: string): string | null {
  const decoded = decodeURIComponent(raw);
  return /^[A-Za-z0-9._-]+$/.test(decoded) ? decoded : null;
}

/** Resolve the demo-media source bucket file for an event (mirrors mediaUrlForStation). */
function sourceBucketFile(stationId: string, ts: Date): string | null {
  const station = stations.find((candidate) => candidate.id === stationId);
  const slug = station?.mediaSlug ?? stationId;
  const day = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Los_Angeles",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(ts);
  const bucket = mediaBucketForTime(ts);
  const base = day === "2026-06-26" ? bucket : `${day.replace(/-/g, "")}-${bucket}`;
  const resolved = path.resolve(demoMediaRoot, slug, `${base}.mp4`);
  // Stay inside demo-media.
  if (!resolved.startsWith(`${path.resolve(demoMediaRoot)}${path.sep}`)) return null;
  return resolved;
}

function extractClip(src: string, startSec: number, durationSec: number, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const args = [
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      "-ss",
      String(startSec),
      "-i",
      src,
      "-t",
      String(durationSec),
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-crf",
      "26",
      "-an",
      "-movflags",
      "+faststart",
      "-pix_fmt",
      "yuv420p",
      dest,
    ];
    const child = spawn(FFMPEG, args);
    let stderr = "";
    child.stderr.on("data", (chunk) => (stderr += chunk.toString()));
    child.on("error", reject);
    child.on("close", (code) => (code === 0 ? resolve() : reject(new Error(stderr || `ffmpeg exited ${code}`))));
  });
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ eventId: string }> },
) {
  const { eventId: rawId } = await params;
  const eventId = sanitizeEventId(rawId);
  if (!eventId) {
    return new Response("Invalid clip id", { status: 400 });
  }

  const event = findEventByClipId(eventId);
  if (!event) {
    return new Response("Clip not found", { status: 404 });
  }

  const ts = new Date(event.ts);
  const src = sourceBucketFile(event.station_id, ts);
  if (!src) {
    return new Response("Invalid source path", { status: 400 });
  }
  try {
    await stat(src);
  } catch {
    return new Response("Source footage not available", { status: 404 });
  }

  // The bucket mp4 is a 60s loop; place the event by its within-minute offset.
  const withinMinute = ((event.demo_offset_sec % 60) + 60) % 60;
  const startSec = Math.max(0, withinMinute - CLIP_PAD_SEC);
  const durationSec = CLIP_PAD_SEC * 2;

  await mkdir(cacheRoot, { recursive: true });
  const dest = path.join(cacheRoot, `${eventId}.mp4`);

  let cached = false;
  try {
    await stat(dest);
    cached = true;
  } catch {
    cached = false;
  }
  if (!cached) {
    try {
      await extractClip(src, startSec, durationSec, dest);
    } catch (error) {
      console.error("clip extraction failed:", error);
      return new Response("Could not extract clip", { status: 500 });
    }
  }

  const size = statSync(dest).size;
  const range = _request.headers.get("range");
  const filename = `${event.station_id}-${eventId}.mp4`;
  const baseHeaders: Record<string, string> = {
    "Accept-Ranges": "bytes",
    "Content-Type": "video/mp4",
    "Content-Disposition": `attachment; filename="${filename}"`,
    "Cache-Control": "no-store",
  };

  if (!range) {
    return new Response(Readable.toWeb(createReadStream(dest)) as BodyInit, {
      status: 200,
      headers: { ...baseHeaders, "Content-Length": String(size) },
    });
  }

  const match = range.match(/^bytes=(\d*)-(\d*)$/);
  if (!match) {
    return new Response("Invalid range", { status: 416 });
  }
  const start = match[1] ? Number(match[1]) : 0;
  const end = match[2] ? Number(match[2]) : size - 1;
  if (start > end || end >= size) {
    return new Response("Range not satisfiable", {
      status: 416,
      headers: { "Content-Range": `bytes */${size}` },
    });
  }

  return new Response(Readable.toWeb(createReadStream(dest, { start, end })) as BodyInit, {
    status: 206,
    headers: {
      ...baseHeaders,
      "Content-Range": `bytes ${start}-${end}/${size}`,
      "Content-Length": String(end - start + 1),
    },
  });
}
