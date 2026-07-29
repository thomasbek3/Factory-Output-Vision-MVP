import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { StationWorkforceSurface } from "@/components/owner-v2/station-workforce-surface";
import {
  ownerPreviewDashboard,
  ownerPreviewStationFor,
} from "@/lib/preview/ownerDashboard";

export default async function OwnerStationsPreviewPage({
  searchParams,
}: {
  searchParams: Promise<{ station_id?: string; state?: string }>;
}) {
  const params = await searchParams;
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <StationWorkforceSurface
        data={ownerPreviewStationFor(params.station_id, params.state)}
        preview
      />
    </OwnerShell>
  );
}
