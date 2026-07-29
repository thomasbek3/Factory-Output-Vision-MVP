import { OwnerSurfaceState } from "@/components/owner-v2/owner-surface-state";

export default function SettingsPage() {
  return (
    <OwnerSurfaceState
      title="Settings"
      description="Factory timezone, verification-lag thresholds, retention, and authorized owner access will be managed here with an audit trail."
    />
  );
}
