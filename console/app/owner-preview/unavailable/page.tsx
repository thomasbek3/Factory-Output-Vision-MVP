import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { OwnerDataUnavailable } from "@/components/owner-v2/owner-surface-state";

export default function OwnerUnavailablePreviewPage() {
  return (
    <OwnerShell factories={[]} preview status="unavailable">
      <OwnerDataUnavailable />
    </OwnerShell>
  );
}
