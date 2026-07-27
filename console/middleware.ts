import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PORTAL_PREFIXES = [
  "/review",
  "/ops",
  "/api/review",
  "/api/ops",
];

function isPublicPortalPath(pathname: string) {
  return PUBLIC_PORTAL_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  if (process.env.FV_PUBLIC_PORTAL_ONLY !== "1") {
    return NextResponse.next();
  }

  if (isPublicPortalPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return new NextResponse(null, { status: 404 });
  }

  return NextResponse.redirect(new URL("/review", request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
