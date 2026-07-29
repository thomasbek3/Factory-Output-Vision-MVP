import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { TodayDashboard } from "@/components/owner-v2/today-dashboard";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

export default function OwnerEmptyPreviewPage() {
  const data = {
    ...ownerPreviewDashboard,
    projects: [],
    attention: [],
    exceptionMonitoringAvailable: false,
    stations: [],
  };
  return (
    <OwnerShell
      factories={[{ id: data.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <TodayDashboard
        data={data}
        stationOptions={[]}
        workers={[]}
        preview
      />
    </OwnerShell>
  );
}
