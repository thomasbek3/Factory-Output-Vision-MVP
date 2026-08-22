import { NextRequest } from "next/server";
import {
  authorizeReviewerAccessToken,
  reviewerAccessToken,
} from "@/lib/reviewServer";
import { callWorkerRpc, workerPortalError } from "@/lib/workerPortalServer";

export const dynamic = "force-dynamic";

async function rpc(request: NextRequest, functionName: string, body: object) {
  const token = reviewerAccessToken(request);
  if (!token) throw new Error("AUTH_REQUIRED");
  if (!(await authorizeReviewerAccessToken(token))) {
    throw new Error("ACCESS_DISABLED");
  }
  try {
    return await callWorkerRpc(functionName, body, { accessToken: token });
  } catch (error) {
    const status = (error as { status?: number }).status;
    throw workerPortalError(
      error instanceof Error ? error.message : `ONBOARDING_${status ?? "FAILED"}`,
      status,
    );
  }
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
