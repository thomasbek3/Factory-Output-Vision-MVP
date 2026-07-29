import {
  FactoryChooser,
  OwnerDataUnavailable,
  OwnerNoFactories,
  OwnerSurfaceState,
} from "@/components/owner-v2/owner-surface-state";
import { StationWorkforceSurface } from "@/components/owner-v2/station-workforce-surface";
import { resolveOwnerPageContext } from "@/lib/ownerPageContext";
import { loadOwnerStationData } from "@/lib/ownerStationServer";

export default async function StationsPage({
  searchParams,
}: {
  searchParams: Promise<{
    factory_id?: string;
    station_id?: string;
    assignment_id?: string;
    date?: string;
  }>;
}) {
  const params = await searchParams;
  const query = new URLSearchParams();
  if (params.factory_id) query.set("factory_id", params.factory_id);
  if (params.station_id) query.set("station_id", params.station_id);
  if (params.assignment_id) query.set("assignment_id", params.assignment_id);
  if (params.date) query.set("date", params.date);
  const returnTo = query.size ? `/stations?${query.toString()}` : "/stations";
  const context = await resolveOwnerPageContext({
    requestedFactoryId: params.factory_id,
    returnTo,
  });
  if (context.kind === "unavailable") return <OwnerDataUnavailable />;
  if (context.kind === "none") return <OwnerNoFactories />;
  if (context.kind === "choose") {
    return <FactoryChooser factories={context.factories} basePath="/stations" />;
  }
  let result;
  try {
    result = await loadOwnerStationData({
      accessToken: context.accessToken,
      factoryId: context.factory.id,
      timezone: context.factory.timezone,
      stationId: params.station_id,
      assignmentId: params.assignment_id,
      selectedDate: params.date,
    });
  } catch {
    return <OwnerDataUnavailable />;
  }
  if (result.kind === "no_stations") {
    return (
      <OwnerSurfaceState
        title="No stations configured"
        description="Add an active production station before assigning a project or reviewing verified station output."
      />
    );
  }
  if (result.kind === "no_assignment") {
    return (
      <OwnerSurfaceState
        title="No project assigned"
        description={`${result.stationName} has no project assignment for the selected date. No shift or production values were inferred.`}
      />
    );
  }
  return <StationWorkforceSurface data={result.data} />;
}
