import { createReadStream, statSync } from "node:fs";
import { stat } from "node:fs/promises";
import path from "node:path";
import { Readable } from "node:stream";
import { NextRequest } from "next/server";

const mediaRoot = path.join(process.cwd(), "demo-media");

function safeMediaPath(parts: string[]) {
  const resolved = path.resolve(mediaRoot, ...parts);
  const root = path.resolve(mediaRoot);
  if (!resolved.startsWith(`${root}${path.sep}`)) {
    return null;
  }
  return resolved;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path: parts } = await params;
  const filePath = safeMediaPath(parts);

  if (!filePath) {
    return new Response("Invalid media path", { status: 400 });
  }

  try {
    await stat(filePath);
  } catch {
    return new Response("Media not found", { status: 404 });
  }

  const size = statSync(filePath).size;
  const range = request.headers.get("range");
  const headers = {
    "Accept-Ranges": "bytes",
    "Content-Type": "video/mp4",
    "Cache-Control": "public, max-age=3600",
  };

  if (!range) {
    return new Response(Readable.toWeb(createReadStream(filePath)) as BodyInit, {
      status: 200,
      headers: {
        ...headers,
        "Content-Length": String(size),
      },
    });
  }

  const match = range.match(/^bytes=(\d*)-(\d*)$/);
  if (!match) {
    return new Response("Malformed range", { status: 416 });
  }

  const start = match[1] ? Number(match[1]) : 0;
  const end = match[2] ? Number(match[2]) : size - 1;

  if (Number.isNaN(start) || Number.isNaN(end) || start > end || end >= size) {
    return new Response("Range not satisfiable", {
      status: 416,
      headers: { "Content-Range": `bytes */${size}` },
    });
  }

  return new Response(
    Readable.toWeb(createReadStream(filePath, { start, end })) as BodyInit,
    {
      status: 206,
      headers: {
        ...headers,
        "Content-Length": String(end - start + 1),
        "Content-Range": `bytes ${start}-${end}/${size}`,
      },
    },
  );
}
