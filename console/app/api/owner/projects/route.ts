import { NextRequest } from "next/server";
import {
  normalizeOwnerProjectDraft,
  ownerProjectRpcPayload,
  validateOwnerProjectDraft,
} from "@/lib/ownerProjectForm";
import {
  authorizeOwner,
  OwnerDataError,
  ownerRestAll,
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

function unavailable() {
  return Response.json({ error: "OWNER_DATA_UNAVAILABLE" }, { status: 503 });
}

function ownerFailure(error: unknown) {
  if (error instanceof OwnerDataError) {
    return Response.json(
      { error: error.publicCode },
      { status: error.status },
    );
  }
  return unavailable();
}

export async function GET(request: NextRequest) {
  const factoryId = factoryIdFrom(request);
  const factoryIdFailure = invalidFactoryId(factoryId);
  if (factoryIdFailure) return factoryIdFailure;

  try {
    const authorization = await authorizeOwner(request, factoryId);
    if (!authorization.authorized) {
      return Response.json(
        { error: authorization.status === 401 ? "OWNER_AUTH_REQUIRED" : "OWNER_ACCESS_DENIED" },
        { status: authorization.status },
      );
    }
    const query = new URLSearchParams({
      factory_id: `eq.${factoryId}`,
      select: "*",
      order: "created_at.desc,id.desc",
    });
    const projects = await ownerRestAll<unknown>(
      authorization.accessToken,
      `owner_projects?${query.toString()}`,
    );
    return Response.json({ projects });
  } catch (error) {
    console.error("GET /api/owner/projects failed:", error);
    return ownerFailure(error);
  }
}

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json({ error: "OWNER_ORIGIN_INVALID" }, { status: 403 });
  }
  const factoryId = factoryIdFrom(request);
  const factoryIdFailure = invalidFactoryId(factoryId);
  if (factoryIdFailure) return factoryIdFailure;

  try {
    const authorization = await authorizeOwner(request, factoryId);
    if (!authorization.authorized) {
      return Response.json(
        { error: authorization.status === 401 ? "OWNER_AUTH_REQUIRED" : "OWNER_ACCESS_DENIED" },
        { status: authorization.status },
      );
    }
    const body = (await request.json()) as Record<string, unknown>;
    const draft = normalizeOwnerProjectDraft({ ...body, factoryId });
    const validation = validateOwnerProjectDraft(draft);
    if (!validation.ok) {
      return Response.json(
        { error: "OWNER_PROJECT_INVALID", errors: validation.errors },
        { status: 422 },
      );
    }
    const project = await ownerRpc<unknown>(
      authorization.accessToken,
      "owner_start_project",
      ownerProjectRpcPayload(draft, "open"),
    );
    return Response.json({ project }, { status: 201 });
  } catch (error) {
    console.error("POST /api/owner/projects failed:", error);
    return ownerFailure(error);
  }
}
