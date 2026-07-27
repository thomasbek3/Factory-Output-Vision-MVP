import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";
import {
  authorizeReviewerAccessToken,
  reviewServerConfig,
  reviewerAccessToken,
  reviewerRefreshToken,
  setReviewerCookies,
} from "@/lib/reviewServer";

export const dynamic = "force-dynamic";

async function authenticatedClient(request: NextRequest) {
  const accessToken = reviewerAccessToken(request);
  const refreshToken = reviewerRefreshToken(request);
  if (!accessToken || !refreshToken) throw new Error("AUTH_REQUIRED");
  if (!(await authorizeReviewerAccessToken(accessToken))) {
    throw new Error("ACCESS_DISABLED");
  }
  const config = reviewServerConfig();
  const client = createClient(config.projectUrl, config.publishableKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  const { error } = await client.auth.setSession({
    access_token: accessToken,
    refresh_token: refreshToken,
  });
  if (error) throw error;
  return client;
}

function failed(error: unknown) {
  const message = error instanceof Error ? error.message : "MFA_FAILED";
  return Response.json({ error: message }, { status: message === "AUTH_REQUIRED" ? 401 : 400 });
}

export async function GET(request: NextRequest) {
  try {
    const client = await authenticatedClient(request);
    const [factors, assurance] = await Promise.all([
      client.auth.mfa.listFactors(),
      client.auth.mfa.getAuthenticatorAssuranceLevel(),
    ]);
    if (factors.error) throw factors.error;
    if (assurance.error) throw assurance.error;
    return Response.json({
      currentLevel: assurance.data.currentLevel,
      nextLevel: assurance.data.nextLevel,
      factors: factors.data.totp.map((factor) => ({
        id: factor.id,
        status: factor.status,
        friendlyName: factor.friendly_name,
      })),
    });
  } catch (error) {
    return failed(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      action?: "enroll" | "verify";
      factorId?: string;
      code?: string;
    };
    const client = await authenticatedClient(request);
    if (body.action === "enroll") {
      const enrolled = await client.auth.mfa.enroll({
        factorType: "totp",
        friendlyName: "FactoryVision Reviewer",
      });
      if (enrolled.error) throw enrolled.error;
      return Response.json({
        factorId: enrolled.data.id,
        qrCode: enrolled.data.totp.qr_code,
        secret: enrolled.data.totp.secret,
      });
    }
    if (body.action !== "verify" || !body.factorId || !body.code?.match(/^\d{6}$/)) {
      return Response.json({ error: "INVALID_MFA_REQUEST" }, { status: 422 });
    }
    const verified = await client.auth.mfa.challengeAndVerify({
      factorId: body.factorId,
      code: body.code,
    });
    if (verified.error) throw verified.error;
    const sessionResult = await client.auth.getSession();
    const session = sessionResult.data.session;
    if (!session) throw new Error("MFA_SESSION_MISSING");
    const output = NextResponse.json({ verified: true });
    setReviewerCookies(
      request,
      output,
      session.access_token,
      session.refresh_token,
      session.expires_in ?? 3600,
    );
    return output;
  } catch (error) {
    return failed(error);
  }
}
