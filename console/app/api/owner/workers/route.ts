import { NextRequest } from "next/server";
import { isUuid } from "@/lib/identifiers";
import {
  authorizeOwner,
  OwnerDataError,
  ownerRestAll,
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

function factoryIdFrom(request: NextRequest) {
  return request.nextUrl.searchParams.get("factory_id")?.trim() ?? "";
}

async function ownerAccess(request: NextRequest, factoryId: string) {
  if (!factoryId) {
    return {
      ok: false as const,
      response: Response.json(
        { error: "FACTORY_ID_REQUIRED" },
        { status: 400 },
      ),
    };
  }
  if (!isUuid(factoryId)) {
    return {
      ok: false as const,
      response: Response.json(
        { error: "FACTORY_ID_INVALID" },
        { status: 422 },
      ),
    };
  }
  const authorization = await authorizeOwner(request, factoryId);
  if (!authorization.authorized) {
    return {
      ok: false as const,
      response: Response.json(
        {
          error:
            authorization.status === 401
              ? "OWNER_AUTH_REQUIRED"
              : "OWNER_ACCESS_DENIED",
        },
        { status: authorization.status },
      ),
    };
  }
  return { ok: true as const, accessToken: authorization.accessToken };
}

export async function GET(request: NextRequest) {
  const factoryId = factoryIdFrom(request);
  try {
    const access = await ownerAccess(request, factoryId);
    if (!access.ok) return access.response;
    const query = new URLSearchParams({
      factory_id: `eq.${factoryId}`,
      select:
        "id,display_name,employee_code,primary_role,status,created_at,updated_at",
      order: "display_name.asc,id.asc",
    });
    const workers = await ownerRestAll<unknown>(
      access.accessToken,
      `owner_workers?${query.toString()}`,
    );
    return Response.json({ workers });
  } catch (error) {
    return failure(error);
  }
}

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json({ error: "OWNER_ORIGIN_INVALID" }, { status: 403 });
  }
  const factoryId = factoryIdFrom(request);
  try {
    const access = await ownerAccess(request, factoryId);
    if (!access.ok) return access.response;
    const body = (await request.json().catch(() => null)) as {
      id?: unknown;
      displayName?: unknown;
      employeeCode?: unknown;
      primaryRole?: unknown;
      status?: unknown;
    } | null;
    const workerId =
      typeof body?.id === "string" && body.id.trim() ? body.id.trim() : null;
    const displayName =
      typeof body?.displayName === "string" ? body.displayName.trim() : "";
    const employeeCode =
      typeof body?.employeeCode === "string"
        ? body.employeeCode.trim() || null
        : null;
    const employeeCodeSupplied =
      body !== null
      && Object.prototype.hasOwnProperty.call(body, "employeeCode");
    const primaryRole =
      typeof body?.primaryRole === "string"
        ? body.primaryRole.trim() || null
        : null;
    const primaryRoleSupplied =
      body !== null
      && Object.prototype.hasOwnProperty.call(body, "primaryRole");
    const status = body?.status === "inactive" ? "inactive" : "active";
    if (
      (workerId !== null && !isUuid(workerId))
      || !displayName
      || displayName.length > 200
      || (
        employeeCodeSupplied
        && body?.employeeCode !== null
        && typeof body?.employeeCode !== "string"
      )
      || (employeeCode !== null && employeeCode.length > 100)
      || (
        primaryRoleSupplied
        && body?.primaryRole !== null
        && typeof body?.primaryRole !== "string"
      )
      || (primaryRole !== null && primaryRole.length > 100)
      || (body?.status !== undefined
        && body.status !== "active"
        && body.status !== "inactive")
    ) {
      return Response.json(
        { error: "OWNER_WORKER_INVALID" },
        { status: 422 },
      );
    }

    const worker = await ownerRpc<unknown>(
      access.accessToken,
      "owner_upsert_worker",
      {
        p_factory_id: factoryId,
        p_worker_id: workerId,
        p_display_name: displayName,
        p_employee_code: employeeCode,
        p_primary_role: primaryRole,
        p_status: status,
        p_employee_code_supplied: employeeCodeSupplied,
        p_primary_role_supplied: primaryRoleSupplied,
      },
    );
    return Response.json({ worker }, { status: workerId ? 200 : 201 });
  } catch (error) {
    return failure(error);
  }
}
