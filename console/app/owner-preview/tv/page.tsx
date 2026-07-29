import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerSurfaceState } from "@/components/owner-v2/owner-surface-state";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

export default function OwnerTvPreviewPage() {
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <OwnerSurfaceState
        title="Owner display preview"
        description="Preview data for a read-only factory-floor display. Production TV remains outside the authenticated owner route graph."
      />
    </OwnerShell>
  );
}
