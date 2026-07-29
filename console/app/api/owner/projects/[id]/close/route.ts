import { NextRequest } from "next/server";
import { isUuid } from "@/lib/identifiers";
import {
  authorizeOwner,
  OwnerDataError,
  ownerRpc,
} from "@/lib/ownerServer";

export const dynamic = "force-dynamic";

function failure(error: unknown) {
  if (error instanceof OwnerDataError) {
    return Response.json(
      { error: error.publicCode },
      { status: error.status },
    );
  }
  return Response.json({ error: "OWNER_DATA_UNAVAILABLE" }, { status: 503 });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json({ error: "OWNER_ORIGIN_INVALID" }, { status: 403 });
  }
  const factoryId =
    request.nextUrl.searchParams.get("factory_id")?.trim() ?? "";
  const { id: projectId } = await context.params;
  if (!factoryId) {
    return Response.json({ error: "FACTORY_ID_REQUIRED" }, { status: 400 });
  }
  if (!isUuid(factoryId) || !isUuid(projectId)) {
    return Response.json({ error: "OWNER_ID_INVALID" }, { status: 422 });
  }

  try {
    const authorization = await authorizeOwner(request, factoryId);
    if (!authorization.authorized) {
      return Response.json(
        {
          error:
            authorization.status === 401
              ? "OWNER_AUTH_REQUIRED"
              : "OWNER_ACCESS_DENIED",
        },
        { status: authorization.status },
      );
    }
    const payload = (await request.json().catch(() => null)) as {
      actualMaterialCostCents?: unknown;
      completedAt?: unknown;
    } | null;
    const actualMaterialCostCents = payload?.actualMaterialCostCents;
    const completedAt =
      typeof payload?.completedAt === "string"
        ? payload.completedAt.trim()
        : new Date().toISOString();
    const completedAtMs = Date.parse(completedAt);
    if (
      typeof actualMaterialCostCents !== "number"
      || !Number.isSafeInteger(actualMaterialCostCents)
      || actualMaterialCostCents < 0
      || !completedAt
      || Number.isNaN(completedAtMs)
      || completedAtMs > Date.now() + 5 * 60 * 1000
    ) {
      return Response.json(
        { error: "OWNER_CLOSEOUT_INVALID" },
        { status: 422 },
      );
    }

    const closeout = await ownerRpc<unknown>(
      authorization.accessToken,
      "owner_close_project",
      {
        p_factory_id: factoryId,
        p_project_id: projectId,
        p_actual_material_cost_cents: actualMaterialCostCents,
        p_completed_at: completedAt,
      },
    );
    return Response.json({ closeout }, { status: 201 });
  } catch (error) {
    return failure(error);
  }
}
