export type PasswordlessLanguage = "en" | "es";

export function passwordlessRedirectUrl(
  baseUrl: string,
  language: PasswordlessLanguage,
) {
  const redirect = new URL("/review/welcome", baseUrl);
  redirect.searchParams.set("mode", "login");
  redirect.searchParams.set("lang", language);
  return redirect.toString();
}

export function normalizeReviewerEmail(email: string) {
  return email.trim().toLowerCase();
}

export function isPlausibleReviewerEmail(email: string) {
  return email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function passwordlessPublicBaseUrl(
  configuredBaseUrl: string | undefined,
  requestOrigin: string,
  production: boolean,
) {
  if (configuredBaseUrl) return new URL(configuredBaseUrl).origin;
  if (production) {
    throw new Error("REVIEW_PUBLIC_BASE_URL is required in production.");
  }
  return new URL(requestOrigin).origin;
}
