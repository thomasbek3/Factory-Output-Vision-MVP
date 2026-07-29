import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerSurfaceState } from "@/components/owner-v2/owner-surface-state";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

export default function OwnerSettingsPreviewPage() {
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <OwnerSurfaceState
        title="Settings preview"
        description="Preview data for factory preferences, shifts, costs, and owner access. No live owner API is called."
      />
    </OwnerShell>
  );
}
