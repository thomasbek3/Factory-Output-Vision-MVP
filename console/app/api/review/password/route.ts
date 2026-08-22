import { NextRequest } from "next/server";
import {
  authorizeReviewerAccessToken,
  reviewerAccessToken,
} from "@/lib/reviewServer";
import { authFetch } from "@/lib/workerPortalServer";

export async function POST(request: NextRequest) {
  const token = reviewerAccessToken(request);
  if (!token) return Response.json({ error: "AUTH_REQUIRED" }, { status: 401 });
  if (!(await authorizeReviewerAccessToken(token))) {
    return Response.json({ error: "ACCESS_DISABLED" }, { status: 403 });
  }
  const body = (await request.json()) as { password?: string };
  if (!body.password || body.password.length < 12) {
    return Response.json({ error: "Password must contain at least 12 characters." }, { status: 422 });
  }
  const response = await authFetch("/user", {
    method: "PUT",
    bearerToken: token,
    body: JSON.stringify({ password: body.password }),
  });
  if (!response.ok) {
    const result = (await response.json()) as { msg?: string; message?: string };
    return Response.json({ error: result.msg ?? result.message ?? "Password update failed." }, { status: 400 });
  }
  return Response.json({ updated: true });
}
