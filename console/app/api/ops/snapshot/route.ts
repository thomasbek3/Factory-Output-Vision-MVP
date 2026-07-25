import { demoNowIso } from "@/lib/demoData";
import { opsSnapshot } from "@/lib/reviewStore";

export const dynamic = "force-dynamic";

export async function GET() {
  const snapshot = opsSnapshot(new Date(demoNowIso));
  return Response.json({
    factories: snapshot.factories,
    camerasUp: snapshot.camerasUp,
    camerasTotal: snapshot.camerasTotal,
    eventsToday: snapshot.eventsToday,
    verificationLagMinutes: snapshot.verificationLagMinutes,
    openQueueDepth: snapshot.openQueueDepth,
    chunksTotal: snapshot.chunksTotal,
  });
}
