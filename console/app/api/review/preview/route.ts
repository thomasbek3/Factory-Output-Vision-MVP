import { NextRequest } from "next/server";
import { opsRpc } from "@/lib/reviewerAdminServer";
import { hasReviewPreviewPass } from "@/lib/reviewPreviewPass";
import { signStorageUrl, supabaseFetch } from "@/lib/workerPortalServer";

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
  const signed = await signStorageUrl(chunk.mediaBucket, chunk.mediaPath, { kind: "service" }, 60 * 60);
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
      mediaUrl: signed.mediaUrl,
      posterUrl: null,
    },
    actions: [],
    coverage: null,
  };
}

async function servicePracticeChunk() {
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  if (!secretKey) throw new Error("PRACTICE_PREVIEW_NOT_CONFIGURED");
  const response = await supabaseFetch("/rest/v1/rpc/service_latest_practice_preview", {
    method: "POST",
    body: "{}",
    serviceRole: true,
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `PRACTICE_PREVIEW_RPC_${response.status}`);
  }
  return (text ? JSON.parse(text) : null) as PracticeChunk | null;
}

export async function GET(request: NextRequest) {
  try {
    const previewPass = hasReviewPreviewPass(request);
    let chunk: PracticeChunk | null;
    if (previewPass) {
      chunk = await servicePracticeChunk();
    } else {
      await opsRpc<boolean>(request, "ops_assert_access", {
        p_factory_id: null,
      });
      chunk = await opsRpc<PracticeChunk | null>(
        request,
        "ops_latest_practice_preview",
        {},
      );
    }
    const practice = chunk ? await signPracticeMedia(chunk) : null;
    return Response.json({ allowed: true, practice });
  } catch {
    return Response.json({ error: "OPS_ACCESS_REQUIRED" }, { status: 403 });
  }
}
