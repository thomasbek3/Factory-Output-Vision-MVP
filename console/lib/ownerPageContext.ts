import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  authorizeOwnerAccessToken,
  ownerAccessCookie,
  OwnerDataError,
  ownerRefreshCookie,
} from "@/lib/ownerServer";
import {
  selectOwnerFactory,
  type OwnerFactorySelection,
} from "@/lib/ownerFactorySelection";

export type OwnerFactoryContext = OwnerFactorySelection;

export async function resolveOwnerPageContext(input: {
  requestedFactoryId?: string;
  returnTo: string;
}) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ownerAccessCookie)?.value;
  if (!accessToken) redirect("/sign-in");
  let authorization;
  try {
    authorization = await authorizeOwnerAccessToken(accessToken);
  } catch (error) {
    if (
      error instanceof OwnerDataError
      && error.status === 401
      && cookieStore.get(ownerRefreshCookie)?.value
    ) {
      redirect(
        `/api/owner/session?action=refresh&return_to=${encodeURIComponent(input.returnTo)}`,
      );
    }
    return { kind: "unavailable" as const };
  }
  if (!authorization.authorized) {
    if (
      authorization.status === 401
      && cookieStore.get(ownerRefreshCookie)?.value
    ) {
      redirect(
        `/api/owner/session?action=refresh&return_to=${encodeURIComponent(input.returnTo)}`,
      );
    }
    redirect("/sign-in");
  }
  const factories = authorization.factories as OwnerFactoryContext[];
  const selection = selectOwnerFactory(factories, input.requestedFactoryId);
  if (selection.kind !== "ready") return selection;
  return {
    kind: "ready" as const,
    accessToken,
    factory: selection.factory,
  };
}
