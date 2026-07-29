import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { TodayDashboard } from "@/components/owner-v2/today-dashboard";
import { ownerDashboardFromDurableProjects } from "@/lib/ownerDashboardLive";

export default function OwnerLiveTruthPreviewPage() {
  const data = ownerDashboardFromDurableProjects({
    factoryId: "10000000-0000-0000-0000-000000000009",
    timezone: "Invalid/Factory-Timezone",
    nowIso: "2026-05-15T18:31:00Z",
    projects: [
      {
        id: "40000000-0000-0000-0000-000000000009",
        name: "Durable Project Record",
        client: "Owner QA",
        target_units: 400,
        deadline: "invalid-deadline",
        status: "open",
      },
    ],
    stations: [
      {
        id: "20000000-0000-0000-0000-000000000009",
        alias: "Durable Station Record",
        status: "active",
      },
    ],
  });

  return (
    <OwnerShell
      factories={[{ id: data.factoryId, name: "Owner truth-state QA" }]}
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
