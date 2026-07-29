import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { TodayDashboard } from "@/components/owner-v2/today-dashboard";
import {
  ownerPreviewDashboard,
  ownerPreviewWorkers,
} from "@/lib/preview/ownerDashboard";

export default async function OwnerPreviewPage({
  searchParams,
}: {
  searchParams: Promise<{ new?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <TodayDashboard
        data={ownerPreviewDashboard}
        stationOptions={ownerPreviewDashboard.stations.map((station, index) => ({
          id: station.id,
          name: station.name,
          baselineUnitsPerDay: [71, 84, 76, 58, 65][index] ?? null,
        }))}
        workers={[...ownerPreviewWorkers]}
        preview
        initialProjectOpen={resolvedSearchParams.new === "1"}
        stationSuggestion={{
          stationId: ownerPreviewDashboard.stations[0]?.id ?? "",
          confidencePercent: 86,
        }}
      />
    </OwnerShell>
  );
}
