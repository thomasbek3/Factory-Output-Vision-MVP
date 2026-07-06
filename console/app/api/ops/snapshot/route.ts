import { demoNowIso } from "@/lib/demoData";
import { opsSnapshot } from "@/lib/reviewStore";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(opsSnapshot(new Date(demoNowIso)));
}
