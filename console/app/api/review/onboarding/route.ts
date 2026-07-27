import { NextRequest } from "next/server";
import {
  authorizeReviewerAccessToken,
  reviewServerConfig,
  reviewerAccessToken,
} from "@/lib/reviewServer";

export const dynamic = "force-dynamic";

async function rpc(request: NextRequest, functionName: string, body: object) {
  const token = reviewerAccessToken(request);
  if (!token) throw new Error("AUTH_REQUIRED");
  if (!(await authorizeReviewerAccessToken(token))) {
    throw new Error("ACCESS_DISABLED");
  }
  const config = reviewServerConfig();
  const response = await fetch(`${config.projectUrl}/rest/v1/rpc/${functionName}`, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await response.text();
  if (!response.ok) throw new Error(text || `ONBOARDING_${response.status}`);
  return text ? JSON.parse(text) : null;
}

function failed(error: unknown) {
  const message = error instanceof Error ? error.message : "ONBOARDING_FAILED";
  return Response.json({ error: message }, { status: message === "AUTH_REQUIRED" ? 401 : 400 });
}

export async function GET(request: NextRequest) {
  try {
    return Response.json(await rpc(request, "worker_lifecycle_state", {}));
  } catch (error) {
    return failed(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      step?: "mfa_verified" | "terms_accepted" | "walkthrough_completed" | "practice_completed";
      termsVersion?: string;
      deviceIdHash?: string;
    };
    if (!body.step) return Response.json({ error: "STEP_REQUIRED" }, { status: 422 });
    return Response.json(await rpc(request, "worker_record_onboarding_step", {
      p_step: body.step,
      p_terms_version: body.termsVersion ?? null,
      p_device_id_hash: body.deviceIdHash ?? null,
      p_training_version: "worker-v1",
    }));
  } catch (error) {
    return failed(error);
  }
}
