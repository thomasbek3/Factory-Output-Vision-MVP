import { NextRequest } from "next/server";
import { reviewServerConfig } from "@/lib/reviewServer";
import { opsRpc } from "@/lib/opsServer";
import { InviteLocale, reviewerInviteEmail } from "@/lib/reviewerEmail";
import {
  invitationIdempotencyKey,
  invitationRedirectUrl,
  invitationTokenHash,
  newInvitationToken,
} from "@/lib/reviewerInviteSecurity";

type AdminLinkResult = {
  user?: { id?: string };
  properties?: { action_link?: string };
  action_link?: string;
  msg?: string;
  error?: string;
};

type SendInviteInput = {
  requestKey: string;
  email: string;
  displayName: string;
  locale: InviteLocale;
  factoryId: string;
  countryCode: string;
  employmentClassification: "" | "employee" | "contractor";
  payBasis: "" | "hourly" | "per_chunk";
};

export { opsRpc };

function emailConfig() {
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  const resendKey = process.env.RESEND_API_KEY;
  const from = process.env.REVIEW_INVITE_FROM;
  const supportEmail = process.env.REVIEW_SUPPORT_EMAIL;
  const baseUrl = process.env.REVIEW_PUBLIC_BASE_URL;
  if (!secretKey || !resendKey || !from || !supportEmail || !baseUrl) {
    throw new Error("EMAIL_DELIVERY_NOT_CONFIGURED");
  }
  return { secretKey, resendKey, from, supportEmail, baseUrl };
}

export function reviewerEmailReadiness() {
  return {
    ready: Boolean(
      process.env.SUPABASE_SECRET_KEY &&
        process.env.RESEND_API_KEY &&
        process.env.REVIEW_INVITE_FROM &&
        process.env.REVIEW_SUPPORT_EMAIL &&
        process.env.REVIEW_PUBLIC_BASE_URL,
    ),
    sender: process.env.REVIEW_INVITE_FROM ?? null,
    supportEmail: process.env.REVIEW_SUPPORT_EMAIL ?? null,
  };
}

export async function reviewerRoster(request: NextRequest) {
  const [roster, supportRequests, metrics, commandCenter] = await Promise.all([
    opsRpc<Record<string, unknown>>(request, "ops_reviewer_roster", {}),
    opsRpc<unknown[]>(request, "ops_reviewer_support_requests", {}),
    opsRpc<Record<string, number>>(request, "ops_workforce_metrics", {}),
    opsRpc<Record<string, unknown>>(request, "ops_command_center", {}),
  ]);
  return { ...roster, supportRequests, metrics, commandCenter };
}

export async function updateReviewerState(
  request: NextRequest,
  userId: string,
  state: string,
  reason: string,
) {
  return opsRpc(request, "ops_set_reviewer_state", {
    p_user_id: userId,
    p_state: state,
    p_reason: reason || null,
  });
}

export async function updateReviewerSupportState(
  request: NextRequest,
  requestId: string,
  status: "acknowledged" | "closed",
) {
  return opsRpc(request, "ops_set_reviewer_support_status", {
    p_request_id: requestId,
    p_status: status,
  });
}

export async function revokeReviewerInvitation(
  request: NextRequest,
  userId: string,
) {
  return opsRpc(request, "ops_revoke_reviewer_invitation", {
    p_user_id: userId,
  });
}

export async function sendReviewerInvite(request: NextRequest, input: SendInviteInput) {
  await opsRpc<boolean>(request, "ops_assert_access", {
    p_factory_id: input.factoryId,
  });
  const delivery = emailConfig();
  const config = reviewServerConfig();
  const existing = await opsRpc<{
    invitationId: string;
    status: string;
    deliveryId: string | null;
    expiresAt: string;
  } | null>(request, "ops_reviewer_invitation_request", {
    p_request_key: input.requestKey,
  });
  if (existing?.status === "sent") {
    return {
      invitationId: existing.invitationId,
      deliveryId: existing.deliveryId,
      expiresAt: existing.expiresAt,
      replayed: true,
    };
  }
  if (existing) {
    throw new Error(
      existing.status === "delivery_failed"
        ? "INVITATION_DELIVERY_FAILED_REISSUE"
        : "INVITATION_DELIVERY_OUTCOME_UNKNOWN",
    );
  }

  const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();
  const invitationToken = newInvitationToken();
  const redirectTo = invitationRedirectUrl(
    delivery.baseUrl,
    invitationToken,
    input.locale,
  );
  const linkResponse = await fetch(`${config.projectUrl}/auth/v1/admin/generate_link`, {
    method: "POST",
    headers: {
      apikey: delivery.secretKey,
      Authorization: `Bearer ${delivery.secretKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      type: "invite",
      email: input.email,
      redirect_to: redirectTo,
      data: {
        display_name: input.displayName,
        locale: input.locale,
        factory_id: input.factoryId,
      },
    }),
    cache: "no-store",
  });
  const link = (await linkResponse.json()) as AdminLinkResult;
  const actionUrl = link.properties?.action_link ?? link.action_link;
  const userId = link.user?.id;
  if (!linkResponse.ok || !actionUrl || !userId) {
    throw new Error(link.msg ?? link.error ?? "INVITE_LINK_FAILED");
  }

  const email = reviewerInviteEmail({
    displayName: input.displayName,
    actionUrl,
    expiresAt,
    locale: input.locale,
    supportEmail: delivery.supportEmail,
  });
  const invitationId = await opsRpc<string>(
    request,
    "service_register_reviewer_invitation",
    {
      p_user_id: userId,
      p_factory_id: input.factoryId,
      p_email: input.email,
      p_display_name: input.displayName,
      p_locale: input.locale,
      p_country_code: input.countryCode,
      p_employment_classification: input.employmentClassification,
      p_pay_basis: input.payBasis,
      p_expires_at: expiresAt,
      p_delivery_provider: null,
      p_delivery_id: null,
      p_invitation_token_hash: invitationTokenHash(invitationToken),
      p_request_key: input.requestKey,
    },
  );
  const claim = await opsRpc<{ claimed: boolean; status: string }>(
    request,
    "ops_claim_reviewer_invitation_delivery",
    { p_invitation_id: invitationId },
  );
  if (!claim.claimed) {
    throw new Error("INVITATION_DELIVERY_OUTCOME_UNKNOWN");
  }

  let sent: { id?: string; message?: string };
  try {
    const sendResponse = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${delivery.resendKey}`,
        "Content-Type": "application/json",
        "Idempotency-Key": invitationIdempotencyKey(invitationId),
      },
      body: JSON.stringify({
        from: delivery.from,
        to: [input.email],
        reply_to: delivery.supportEmail,
        subject: email.subject,
        html: email.html,
        text: email.text,
        headers: { "X-Entity-Ref-ID": invitationId },
      }),
      cache: "no-store",
    });
    sent = (await sendResponse.json()) as { id?: string; message?: string };
    if (!sendResponse.ok || !sent.id) {
      throw new Error(sent.message ?? "INVITE_DELIVERY_FAILED");
    }
  } catch (error) {
    await opsRpc(request, "ops_mark_reviewer_invitation_delivery", {
      p_invitation_id: invitationId,
      p_status: "delivery_failed",
      p_delivery_provider: "resend",
      p_delivery_id: null,
    }).catch(() => undefined);
    throw error;
  }

  await opsRpc(request, "ops_mark_reviewer_invitation_delivery", {
    p_invitation_id: invitationId,
    p_status: "sent",
    p_delivery_provider: "resend",
    p_delivery_id: sent.id,
  });
  return { invitationId, deliveryId: sent.id, expiresAt };
}
