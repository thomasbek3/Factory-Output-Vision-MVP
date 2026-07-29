import { NextRequest } from "next/server";
import { opsRpc } from "@/lib/reviewerAdminServer";
import { authorizeOps } from "@/lib/opsServer";
import { hasReviewPreviewPass } from "@/lib/reviewPreviewPass";
import { reviewServerConfig } from "@/lib/reviewServer";

export const dynamic = "force-dynamic";

type PracticeChunk = {
  chunkId: string;
  stationId: string;
  stationName: string;
  factoryTimezone: string;
  startIso: string;
  endIso: string;
  sourceStartMs: number;
  sourceEndMs: number;
  renditionSourceStartMs: number;
  renditionSourceEndMs: number;
  sourceSha256: string;
  renditionId: string;
  mediaBucket: string;
  mediaPath: string;
};

async function signPracticeMedia(chunk: PracticeChunk) {
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  if (!secretKey) throw new Error("PRACTICE_PREVIEW_NOT_CONFIGURED");
  const config = reviewServerConfig();
  const objectPath = chunk.mediaPath.split("/").map(encodeURIComponent).join("/");
  const response = await fetch(
    `${config.projectUrl}/storage/v1/object/sign/${encodeURIComponent(chunk.mediaBucket)}/${objectPath}`,
    {
      method: "POST",
      headers: {
        apikey: secretKey,
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ expiresIn: 60 * 60 }),
      cache: "no-store",
    },
  );
  if (!response.ok) throw new Error("PRACTICE_MEDIA_SIGNING_FAILED");
  const result = (await response.json()) as {
    signedURL?: string;
    signedUrl?: string;
  };
  const signedPath = result.signedURL ?? result.signedUrl;
  if (!signedPath) throw new Error("PRACTICE_MEDIA_URL_MISSING");
  const mediaUrl = signedPath.startsWith("http")
    ? signedPath
    : `${config.projectUrl}/storage/v1${signedPath}`;
  return {
    id: `practice-preview-${chunk.chunkId}`,
    leaseToken: "practice-preview",
    leaseExpiresAt: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    chunk: {
      id: chunk.chunkId,
      stationId: chunk.stationId,
      stationName: chunk.stationName,
      factoryTimezone: chunk.factoryTimezone,
      startIso: chunk.startIso,
      endIso: chunk.endIso,
      sourceStartMs: chunk.sourceStartMs,
      sourceEndMs: chunk.sourceEndMs,
      renditionSourceStartMs: chunk.renditionSourceStartMs,
      renditionSourceEndMs: chunk.renditionSourceEndMs,
      sourceSha256: chunk.sourceSha256,
      renditionId: chunk.renditionId,
      mediaUrl,
      posterUrl: null,
    },
    actions: [],
    coverage: null,
  };
}

async function servicePracticeChunk() {
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  if (!secretKey) throw new Error("PRACTICE_PREVIEW_NOT_CONFIGURED");
  const config = reviewServerConfig();
  const response = await fetch(
    `${config.projectUrl}/rest/v1/rpc/service_latest_practice_preview`,
    {
      method: "POST",
      headers: {
        apikey: secretKey,
        Authorization: `Bearer ${secretKey}`,
        "Content-Type": "application/json",
      },
      body: "{}",
      cache: "no-store",
    },
  );
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `PRACTICE_PREVIEW_RPC_${response.status}`);
  }
  return (text ? JSON.parse(text) : null) as PracticeChunk | null;
}

export async function GET(request: NextRequest) {
  const previewPass = hasReviewPreviewPass(request);
  if (!previewPass) {
    try {
      const authorization = await authorizeOps(request);
      if (!authorization.authorized) {
        return Response.json({ allowed: false, practice: null });
      }
    } catch {
      return Response.json(
        { error: "PRACTICE_PREVIEW_UNAVAILABLE" },
        { status: 503 },
      );
    }
  }

  try {
    let chunk: PracticeChunk | null;
    if (previewPass) {
      chunk = await servicePracticeChunk();
    } else {
      chunk = await opsRpc<PracticeChunk | null>(
        request,
        "ops_latest_practice_preview",
        {},
      );
    }
    const practice = chunk ? await signPracticeMedia(chunk) : null;
    return Response.json({ allowed: true, practice });
  } catch {
    return Response.json(
      { error: "PRACTICE_PREVIEW_UNAVAILABLE" },
      { status: 503 },
    );
  }
}
