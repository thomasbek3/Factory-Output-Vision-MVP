import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { WorkforceDirectory } from "@/components/owner-v2/workforce-directory";
import {
  ownerPreviewDashboard,
  ownerPreviewWorkforce,
} from "@/lib/preview/ownerDashboard";

export default function OwnerWorkforcePreviewPage() {
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <WorkforceDirectory data={ownerPreviewWorkforce} preview />
    </OwnerShell>
  );
}
