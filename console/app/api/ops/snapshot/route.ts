import { NextRequest } from "next/server";
import { opsRpc } from "@/lib/reviewerAdminServer";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    return Response.json(
      await opsRpc(request, "ops_workforce_metrics", {}),
    );
  } catch {
    return Response.json({ error: "Ops authentication required." }, { status: 401 });
  }
}
