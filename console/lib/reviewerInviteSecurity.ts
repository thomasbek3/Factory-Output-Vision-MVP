import { createHash, randomBytes } from "node:crypto";
import type { InviteLocale } from "./reviewerEmail";

export function newInvitationToken() {
  return randomBytes(32).toString("base64url");
}

export function invitationTokenHash(token: string) {
  return createHash("sha256").update(token).digest("hex");
}

export function invitationRedirectUrl(
  baseUrl: string,
  token: string,
  locale: InviteLocale,
) {
  const redirect = new URL("/review/welcome", baseUrl);
  redirect.searchParams.set("invitation", token);
  redirect.searchParams.set("lang", locale === "es-419" ? "es" : "en");
  return redirect.toString();
}

export function invitationIdempotencyKey(invitationId: string) {
  return `factoryvision-invite/${invitationId}`;
}
