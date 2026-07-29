import { NextRequest } from "next/server";
import {
  authorizeOwner,
  OwnerDataError,
  ownerRest,
  ownerRpc,
} from "@/lib/ownerServer";
import { isUuid } from "@/lib/identifiers";

export const dynamic = "force-dynamic";

function factoryIdFrom(request: NextRequest) {
  return request.nextUrl.searchParams.get("factory_id")?.trim() ?? "";
}

function invalidFactoryId(factoryId: string) {
  if (!factoryId) {
    return Response.json({ error: "FACTORY_ID_REQUIRED" }, { status: 400 });
  }
  if (!isUuid(factoryId)) {
    return Response.json({ error: "FACTORY_ID_INVALID" }, { status: 422 });
  }
  return null;
}

function failure(error: unknown) {
  if (error instanceof OwnerDataError) {
    return Response.json(
      { error: error.publicCode },
      { status: error.status },
    );
  }
  return Response.json({ error: "OWNER_DATA_UNAVAILABLE" }, { status: 503 });
}

async function access(request: NextRequest, factoryId: string) {
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
  const factoryIdFailure = invalidFactoryId(factoryId);
  if (factoryIdFailure) return factoryIdFailure;
  try {
    const authorization = await access(request, factoryId);
    if (!authorization.ok) return authorization.response;
    const query = new URLSearchParams({
      factory_id: `eq.${factoryId}`,
      select: "payload",
      limit: "1",
    });
    const rows = await ownerRest<{ payload: Record<string, unknown> }[]>(
      authorization.accessToken,
      `owner_project_drafts?${query.toString()}`,
    );
    return Response.json({ draft: rows[0]?.payload ?? null });
  } catch (error) {
    return failure(error);
  }
}

export async function PUT(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json({ error: "OWNER_ORIGIN_INVALID" }, { status: 403 });
  }
  const factoryId = factoryIdFrom(request);
  const factoryIdFailure = invalidFactoryId(factoryId);
  if (factoryIdFailure) return factoryIdFailure;
  const payload = (await request.json().catch(() => null)) as unknown;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return Response.json({ error: "OWNER_DRAFT_INVALID" }, { status: 422 });
  }
  try {
    const authorization = await access(request, factoryId);
    if (!authorization.ok) return authorization.response;
    const draft = await ownerRpc<Record<string, unknown>>(
      authorization.accessToken,
      "owner_save_project_draft",
      {
        p_factory_id: factoryId,
        p_payload: payload,
      },
    );
    return Response.json({ draft });
  } catch (error) {
    return failure(error);
  }
}
