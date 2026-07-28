import { NextRequest } from "next/server";
import {
  reviewerEmailReadiness,
  reviewerRoster,
  revokeReviewerInvitation,
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
  const publicCode = status === 403 ? "OPS_ACCESS_REQUIRED"
    : status === 503 ? "EMAIL_DELIVERY_NOT_CONFIGURED"
      : message.includes("INVITATION_DELIVERY_FAILED_REISSUE")
        ? "INVITATION_DELIVERY_FAILED_REISSUE"
        : message.includes("INVITATION_DELIVERY_OUTCOME_UNKNOWN")
          ? "INVITATION_DELIVERY_OUTCOME_UNKNOWN"
          : "OPS_REQUEST_FAILED";
  return Response.json({ error: publicCode }, { status });
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
      requestKey?: string;
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
      !body.requestKey?.match(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      ) ||
      !body.email.includes("@")
    ) {
      return Response.json({ error: "INVALID_INVITATION" }, { status: 422 });
    }
    const result = await sendReviewerInvite(request, {
      requestKey: body.requestKey,
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
      revokeInvitationUserId?: string;
    };
    if (body.revokeInvitationUserId) {
      return Response.json(
        await revokeReviewerInvitation(request, body.revokeInvitationUserId),
      );
    }
    if (body.supportRequestId && body.supportStatus) {
      const result = await updateReviewerSupportState(
        request,
        body.supportRequestId,
        body.supportStatus,
      );
      return Response.json(result);
    }
    if (
      !body.userId ||
      !body.state ||
      !["qualification", "active", "suspended", "offboarded"].includes(body.state)
    ) {
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
