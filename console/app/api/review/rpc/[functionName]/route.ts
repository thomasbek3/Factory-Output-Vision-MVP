import { NextRequest } from "next/server";
import { reviewServerConfig, reviewerAccessToken } from "@/lib/reviewServer";

export const dynamic = "force-dynamic";

const workerFunctions = new Set([
  "claim_worker_assignment",
  "heartbeat_worker_assignment",
  "append_worker_action",
  "submit_worker_assignment",
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

async function signAssignmentMedia(
  token: string,
  payload: ClaimPayload,
  config: ReturnType<typeof reviewServerConfig>,
) {
  const chunk = payload.assignment?.chunk;
  if (!chunk) return payload;
  const mediaBucket = chunk.mediaBucket ?? "review-renditions";
  const mediaPath =
    chunk.mediaPath ??
    (chunk.mediaUrl?.startsWith("/api/media/")
      ? chunk.mediaUrl.slice("/api/media/".length)
      : null);
  if (!mediaPath) throw new Error("Assignment media path is unavailable.");
  const objectPath = mediaPath
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  const signed = await fetch(
    `${config.projectUrl}/storage/v1/object/sign/${encodeURIComponent(mediaBucket)}/${objectPath}`,
    {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ expiresIn: 15 * 60 }),
      cache: "no-store",
    },
  );
  if (!signed.ok) throw new Error("Unable to authorize assignment media.");
  const result = (await signed.json()) as { signedURL?: string; signedUrl?: string };
  const signedPath = result.signedURL ?? result.signedUrl;
  if (!signedPath) throw new Error("Media authorization returned no URL.");
  chunk.mediaUrl = signedPath.startsWith("http")
    ? signedPath
    : `${config.projectUrl}/storage/v1${signedPath}`;
  delete chunk.mediaBucket;
  delete chunk.mediaPath;
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
  const config = reviewServerConfig();
  const response = await fetch(
    `${config.projectUrl}/rest/v1/rpc/${functionName}`,
    {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: await request.text(),
      cache: "no-store",
    },
  );
  const text = await response.text();
  if (!response.ok) {
    return new Response(text, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  const payload = text ? (JSON.parse(text) as ClaimPayload) : null;
  const output =
    functionName === "claim_worker_assignment" && payload
      ? await signAssignmentMedia(token, payload, config)
      : payload;
  return Response.json(output);
}
