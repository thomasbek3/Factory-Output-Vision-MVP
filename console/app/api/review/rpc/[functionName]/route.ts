import { NextRequest } from "next/server";
import {
  authorizeReviewerAccessToken,
  reviewerAccessToken,
} from "@/lib/reviewServer";
import { signStorageUrl, supabaseFetch } from "@/lib/workerPortalServer";

export const dynamic = "force-dynamic";

const workerFunctions = new Set([
  "claim_worker_assignment",
  "heartbeat_worker_assignment",
  "append_worker_action",
  "submit_worker_assignment_v2",
  "save_worker_coverage",
  "authorize_worker_media",
  "worker_request_support",
  "worker_touch_work_session",
  "worker_close_work_session",
  "worker_register_active_device",
  "worker_daily_progress",
  "worker_claim_reviewer_qualification",
  "worker_submit_reviewer_qualification",
]);

type ClaimPayload = {
  assignment?: {
    chunk?: {
      mediaBucket?: string;
      mediaPath?: string;
      mediaUrl?: string;
    };
  } | null;
};

type QualificationPayload = {
  qualification?: {
    mediaBucket?: string;
    mediaPath?: string;
    mediaUrl?: string;
  } | null;
};

async function signAssignmentMedia(token: string, payload: ClaimPayload) {
  const chunk = payload.assignment?.chunk;
  if (!chunk) return payload;
  const mediaBucket = chunk.mediaBucket ?? "review-renditions";
  const mediaPath =
    chunk.mediaPath ??
    (chunk.mediaUrl?.startsWith("/api/media/")
      ? chunk.mediaUrl.slice("/api/media/".length)
      : null);
  if (!mediaPath) throw new Error("Assignment media path is unavailable.");
  const signed = await signStorageUrl(mediaBucket, mediaPath, { kind: "reviewer", token }, 10 * 60);
  chunk.mediaUrl = signed.mediaUrl;
  delete chunk.mediaBucket;
  delete chunk.mediaPath;
  return payload;
}

async function signDirectMedia(
  token: string,
  payload: { mediaBucket?: string; mediaPath?: string },
) {
  const wrapped: ClaimPayload = { assignment: { chunk: { ...payload } } };
  await signAssignmentMedia(token, wrapped);
  return { mediaUrl: wrapped.assignment?.chunk?.mediaUrl };
}

async function signQualificationMedia(
  token: string,
  payload: QualificationPayload,
) {
  if (!payload.qualification) return payload;
  const signed = await signDirectMedia(token, payload.qualification);
  payload.qualification.mediaUrl = signed.mediaUrl;
  delete payload.qualification.mediaBucket;
  delete payload.qualification.mediaPath;
  return payload;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ functionName: string }> },
) {
  const { functionName } = await params;
  if (!workerFunctions.has(functionName)) {
    return Response.json({ error: "Unknown worker operation." }, { status: 404 });
  }
  const token = reviewerAccessToken(request);
  if (!token) return Response.json({ error: "Authentication required." }, { status: 401 });
  if (!(await authorizeReviewerAccessToken(token))) {
    return Response.json({ error: "Reviewer access is disabled." }, { status: 403 });
  }
  const response = await supabaseFetch(`/rest/v1/rpc/${functionName}`, {
    method: "POST",
    body: await request.text(),
    accessToken: token,
  });
  const text = await response.text();
  if (!response.ok) {
    return new Response(text, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  const payload = text
    ? (JSON.parse(text) as ClaimPayload & QualificationPayload)
    : null;
  const output =
    functionName === "claim_worker_assignment" && payload
      ? await signAssignmentMedia(token, payload)
      : functionName === "worker_claim_reviewer_qualification" && payload
        ? await signQualificationMedia(token, payload)
      : functionName === "authorize_worker_media" && payload
        ? await signDirectMedia(
            token,
            payload as { mediaBucket?: string; mediaPath?: string },
          )
      : payload;
  return Response.json(output);
}
