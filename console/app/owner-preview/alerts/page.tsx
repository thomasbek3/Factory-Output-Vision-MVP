import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerSurfaceState } from "@/components/owner-v2/owner-surface-state";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

export default function OwnerAlertsPreviewPage() {
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <OwnerSurfaceState
        title="Alerts preview"
        description="Preview data for verification delays, camera outages, and pace exceptions. No live owner API is called."
      />
    </OwnerShell>
  );
}
