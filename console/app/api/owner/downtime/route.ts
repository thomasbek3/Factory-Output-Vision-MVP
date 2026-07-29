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

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json({ error: "OWNER_ORIGIN_INVALID" }, { status: 403 });
  }
  const factoryId =
    request.nextUrl.searchParams.get("factory_id")?.trim() ?? "";
  if (!factoryId) {
    return Response.json({ error: "FACTORY_ID_REQUIRED" }, { status: 400 });
  }
  if (!isUuid(factoryId)) {
    return Response.json({ error: "FACTORY_ID_INVALID" }, { status: 422 });
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
      projectId?: unknown;
      stationId?: unknown;
      effectiveStart?: unknown;
      effectiveEnd?: unknown;
      reasonCode?: unknown;
      note?: unknown;
    } | null;
    const projectId =
      typeof body?.projectId === "string" ? body.projectId.trim() : "";
    const stationId =
      typeof body?.stationId === "string" ? body.stationId.trim() : "";
    const effectiveStart =
      typeof body?.effectiveStart === "string"
        ? body.effectiveStart.trim()
        : "";
    const effectiveEnd =
      typeof body?.effectiveEnd === "string" ? body.effectiveEnd.trim() : "";
    const reasonCode =
      typeof body?.reasonCode === "string" ? body.reasonCode.trim() : "";
    const note = typeof body?.note === "string" ? body.note.trim() : "";
    const startMs = Date.parse(effectiveStart);
    const endMs = Date.parse(effectiveEnd);
    if (
      !isUuid(projectId)
      || !isUuid(stationId)
      || !Number.isFinite(startMs)
      || !Number.isFinite(endMs)
      || endMs <= startMs
      || endMs > Date.now() + 5 * 60_000
      || !reasonCode
      || reasonCode.length > 100
      || note.length > 1_000
    ) {
      return Response.json({ error: "OWNER_DOWNTIME_INVALID" }, { status: 422 });
    }

    const downtime = await ownerRpc<unknown>(
      authorization.accessToken,
      "owner_record_downtime",
      {
        p_factory_id: factoryId,
        p_project_id: projectId,
        p_station_id: stationId,
        p_effective_start: effectiveStart,
        p_effective_end: effectiveEnd,
        p_reason_code: reasonCode,
        p_note: note || null,
      },
    );
    return Response.json({ downtime }, { status: 201 });
  } catch (error) {
    return failure(error);
  }
}
