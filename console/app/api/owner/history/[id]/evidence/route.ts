import { NextRequest } from "next/server";
import { isUuid } from "@/lib/identifiers";
import {
  authorizeOwner,
  OwnerDataError,
  ownerRpc,
  ownerSignedStorageUrl,
} from "@/lib/ownerServer";

export const dynamic = "force-dynamic";

type EvidenceRow = {
  id: string;
  object_sha256: string;
  retention_until: string | null;
  reason_code: string;
  attached_at: string;
  bucket_id: string;
  object_path: string;
  content_type: string;
  byte_size: number;
  status: string;
};

function ownerFailure(error: unknown) {
  if (error instanceof OwnerDataError) {
    return Response.json(
      { error: error.publicCode },
      { status: error.status },
    );
  }
  return Response.json({ error: "OWNER_DATA_UNAVAILABLE" }, { status: 503 });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const factoryId = request.nextUrl.searchParams.get("factory_id")?.trim() ?? "";
  const { id: closeoutId } = await context.params;
  if (!isUuid(factoryId) || !isUuid(closeoutId)) {
    return Response.json({ error: "OWNER_EVIDENCE_INVALID" }, { status: 400 });
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
    const rows = await ownerRpc<EvidenceRow[]>(
      authorization.accessToken,
      "owner_history_evidence",
      { p_factory_id: factoryId, p_closeout_id: closeoutId },
    );
    const now = Date.now();
    const clips = await Promise.all(rows.map(async (row) => {
      const expired =
        row.retention_until !== null
        && Date.parse(row.retention_until) <= now;
      const available = row.status === "verified" && !expired;
      let signed: Awaited<ReturnType<typeof ownerSignedStorageUrl>> | null = null;
      if (available) {
        try {
          signed = await ownerSignedStorageUrl(
            authorization.accessToken,
            row.bucket_id,
            row.object_path,
          );
        } catch (error) {
          console.error("Owner evidence signing failed:", row.id, error);
        }
      }
      return {
        id: row.id,
        objectSha256: row.object_sha256,
        retentionUntil: row.retention_until,
        reasonCode: row.reason_code,
        attachedAt: row.attached_at,
        contentType: row.content_type,
        byteSize: row.byte_size,
        state: expired
          ? "expired"
          : available && signed
            ? "available"
            : "unavailable",
        signedUrl: signed?.signedUrl ?? null,
        expiresIn: signed?.expiresIn ?? null,
      };
    }));
    return Response.json(
      { clips },
      { headers: { "Cache-Control": "private, no-store" } },
    );
  } catch (error) {
    console.error("GET owner closeout evidence failed:", error);
    return ownerFailure(error);
  }
}
