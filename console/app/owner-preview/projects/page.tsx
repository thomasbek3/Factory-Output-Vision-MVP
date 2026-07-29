import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerSurfaceState } from "@/components/owner-v2/owner-surface-state";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

export default function OwnerProjectsPreviewPage() {
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <OwnerSurfaceState
        title="Projects preview"
        description="Preview data for active production projects and their operating plans. No live owner API is called."
      />
    </OwnerShell>
  );
}
