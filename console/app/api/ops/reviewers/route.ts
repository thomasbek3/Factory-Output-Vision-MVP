import { NextRequest } from "next/server";
import {
  reviewerEmailReadiness,
  reviewerRoster,
  sendReviewerInvite,
  updateReviewerState,
  updateReviewerSupportState,
} from "@/lib/reviewerAdminServer";

export const dynamic = "force-dynamic";

function errorResponse(error: unknown) {
  const message = error instanceof Error ? error.message : "OPS_REQUEST_FAILED";
  const status = message.includes("AUTH") || message.includes("ops access") ? 403
    : message.includes("EMAIL_DELIVERY_NOT_CONFIGURED") ? 503
      : 400;
  return Response.json({ error: message }, { status });
}

export async function GET(request: NextRequest) {
  try {
    const roster = await reviewerRoster(request);
    return Response.json({ ...roster, email: reviewerEmailReadiness() });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      email?: string;
      displayName?: string;
      locale?: "en" | "es-419";
      factoryId?: string;
      countryCode?: string;
      employmentClassification?: "" | "employee" | "contractor";
      payBasis?: "" | "hourly" | "per_chunk";
    };
    if (
      !body.email ||
      !body.displayName ||
      !body.factoryId ||
      !body.locale ||
      !body.email.includes("@")
    ) {
      return Response.json({ error: "INVALID_INVITATION" }, { status: 422 });
    }
    const result = await sendReviewerInvite(request, {
      email: body.email.trim().toLowerCase(),
      displayName: body.displayName.trim(),
      locale: body.locale,
      factoryId: body.factoryId,
      countryCode: (body.countryCode ?? "").trim().toUpperCase(),
      employmentClassification: body.employmentClassification ?? "",
      payBasis: body.payBasis ?? "",
    });
    return Response.json(result, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      userId?: string;
      state?: "qualification" | "active" | "suspended" | "offboarded";
      reason?: string;
      supportRequestId?: string;
      supportStatus?: "acknowledged" | "closed";
    };
    if (body.supportRequestId && body.supportStatus) {
      const result = await updateReviewerSupportState(
        request,
        body.supportRequestId,
        body.supportStatus,
      );
      return Response.json(result);
    }
    if (!body.userId || !body.state) {
      return Response.json({ error: "INVALID_STATE_CHANGE" }, { status: 422 });
    }
    const result = await updateReviewerState(
      request,
      body.userId,
      body.state,
      body.reason?.trim() ?? "",
    );
    return Response.json(result);
  } catch (error) {
    return errorResponse(error);
  }
}
