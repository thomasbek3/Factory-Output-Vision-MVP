import { NextRequest } from "next/server";
import { reviewerRoster } from "@/lib/reviewerAdminServer";
import { reviewerInviteEmail } from "@/lib/reviewerEmail";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    await reviewerRoster(request);
  } catch {
    return Response.json({ error: "OPS_AUTH_REQUIRED" }, { status: 403 });
  }
  const locale = request.nextUrl.searchParams.get("locale") === "en" ? "en" : "es-419";
  const email = reviewerInviteEmail({
    displayName: locale === "es-419" ? "Ana Rivera" : "Ana Rivera",
    actionUrl: "https://review.factoryvision.example/review/welcome",
    expiresAt: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    locale,
    supportEmail: "support@factoryvision.example",
  });
  return new Response(email.html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline';",
      "Cache-Control": "no-store",
    },
  });
}

