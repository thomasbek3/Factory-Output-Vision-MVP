import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import React from "react";
import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerDataUnavailable } from "@/components/owner-v2/owner-surface-state";
import {
  authorizeOwnerAccessToken,
  ownerAccessCookie,
  ownerRefreshCookie,
} from "@/lib/ownerServer";

export default async function OwnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const requestedPath =
    (await headers()).get("x-fv-owner-return-to") ?? "/";
  const returnTo =
    requestedPath.startsWith("/")
    && !requestedPath.startsWith("//")
    && !requestedPath.includes("\\")
      ? requestedPath
      : "/";
  const accessToken = cookieStore.get(ownerAccessCookie)?.value;
  if (!accessToken) redirect("/sign-in");
  let authorization;
  try {
    authorization = await authorizeOwnerAccessToken(accessToken);
  } catch {
    return (
      <OwnerShell factories={[]} status="unavailable">
        <OwnerDataUnavailable />
      </OwnerShell>
    );
  }
  if (!authorization.authorized) {
    if (
      authorization.status === 401
      && cookieStore.get(ownerRefreshCookie)?.value
    ) {
      redirect(
        `/api/owner/session?action=refresh&return_to=${encodeURIComponent(returnTo)}`,
      );
    }
    redirect("/sign-in");
  }
  return (
    <OwnerShell
      factories={authorization.factories as { id?: string; name?: string }[]}
    >
      {children}
    </OwnerShell>
  );
}
