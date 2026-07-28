import { NextRequest } from "next/server";
import { opsRpc } from "@/lib/reviewerAdminServer";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    await opsRpc<boolean>(request, "ops_assert_access", {
      p_factory_id: null,
    });
    return Response.json({ allowed: true });
  } catch {
    return Response.json({ error: "OPS_ACCESS_REQUIRED" }, { status: 403 });
  }
}
