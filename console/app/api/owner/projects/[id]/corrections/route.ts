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
    const body = (await request.json().catch(() => null)) as {
      kind?: unknown;
      deltaGoodUnits?: unknown;
      reasonCode?: unknown;
      note?: unknown;
      occurredAt?: unknown;
      actualMaterialCostCents?: unknown;
    } | null;
    const kind = body?.kind;
    const deltaGoodUnits = body?.deltaGoodUnits;
    const reasonCode =
      typeof body?.reasonCode === "string" ? body.reasonCode.trim() : "";
    const note = typeof body?.note === "string" ? body.note.trim() : "";
    const occurredAt =
      typeof body?.occurredAt === "string" ? body.occurredAt.trim() : "";
    const actualMaterialCostCents = body?.actualMaterialCostCents;
    if (
      (kind !== "scrap" && kind !== "rework" && kind !== "correction")
      || typeof deltaGoodUnits !== "number"
      || !Number.isSafeInteger(deltaGoodUnits)
      || deltaGoodUnits === 0
      || ((kind === "scrap" || kind === "rework") && deltaGoodUnits > 0)
      || !reasonCode
      || reasonCode.length > 100
      || !occurredAt
      || Number.isNaN(Date.parse(occurredAt))
      || (
        actualMaterialCostCents !== undefined
        && (
          typeof actualMaterialCostCents !== "number"
          || !Number.isSafeInteger(actualMaterialCostCents)
          || actualMaterialCostCents < 0
        )
      )
    ) {
      return Response.json(
        { error: "OWNER_CORRECTION_INVALID" },
        { status: 422 },
      );
    }

    const closeout = await ownerRpc<unknown>(
      authorization.accessToken,
      "owner_correct_closeout",
      {
        p_factory_id: factoryId,
        p_project_id: projectId,
        p_kind: kind,
        p_delta_good_units: deltaGoodUnits,
        p_reason_code: reasonCode,
        p_note: note || null,
        p_occurred_at: occurredAt,
        p_actual_material_cost_cents:
          actualMaterialCostCents === undefined
            ? null
            : actualMaterialCostCents,
      },
    );
    return Response.json({ closeout }, { status: 201 });
  } catch (error) {
    return failure(error);
  }
}
