import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PREFIXES = [
  "/review",
  "/api/review",
  "/owner-preview",
  "/ops-preview",
];

const PUBLIC_PATHS = new Set([
  "/sign-in",
  "/ops/sign-in",
  "/api/owner/session",
  "/api/ops/session",
]);

function matchesPrefix(pathname: string, prefix: string) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function isPublic(pathname: string) {
  return (
    PUBLIC_PATHS.has(pathname) ||
    PUBLIC_PREFIXES.some((prefix) => matchesPrefix(pathname, prefix))
  );
}

function hasCookie(request: NextRequest, name: string) {
  return Boolean(request.cookies.get(name)?.value);
}

function jwtExpired(token: string) {
  try {
    const payload = token.split(".")[1];
    if (!payload) return false;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    const decoded = JSON.parse(atob(padded)) as { exp?: unknown };
    return (
      typeof decoded.exp === "number"
      && decoded.exp <= Math.floor(Date.now() / 1000) + 30
    );
  } catch {
    return false;
  }
}

function ownerPageResponse(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(
    "x-fv-owner-return-to",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublic(pathname)) return NextResponse.next();

  if (pathname === "/tv" || matchesPrefix(pathname, "/replay")) {
    return new NextResponse(null, { status: 404 });
  }
  if (matchesPrefix(pathname, "/api/jobs")) {
    return new NextResponse(null, { status: 404 });
  }
  if (pathname === "/jobs") {
    return NextResponse.redirect(new URL("/projects", request.url));
  }

  if (matchesPrefix(pathname, "/ops") || matchesPrefix(pathname, "/api/ops")) {
    if (hasCookie(request, "fv_ops_access")) return NextResponse.next();
    if (pathname.startsWith("/api/")) {
      return Response.json({ error: "OPS_AUTH_REQUIRED" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/ops/sign-in", request.url));
  }

  if (matchesPrefix(pathname, "/api/owner")) {
    if (hasCookie(request, "fv_owner_access")) return NextResponse.next();
    return Response.json({ error: "OWNER_AUTH_REQUIRED" }, { status: 401 });
  }

  if (pathname.startsWith("/api/")) {
    return new NextResponse(null, { status: 404 });
  }

  const ownerAccess = request.cookies.get("fv_owner_access")?.value;
  if (ownerAccess) {
    if (jwtExpired(ownerAccess) && hasCookie(request, "fv_owner_refresh")) {
      const refreshUrl = new URL("/api/owner/session", request.url);
      refreshUrl.searchParams.set("action", "refresh");
      refreshUrl.searchParams.set(
        "return_to",
        `${request.nextUrl.pathname}${request.nextUrl.search}`,
      );
      return NextResponse.redirect(refreshUrl);
    }
    return ownerPageResponse(request);
  }
  return NextResponse.redirect(new URL("/sign-in", request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
