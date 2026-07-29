import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  FactoryChooser,
  OwnerDataUnavailable,
  OwnerNoFactories,
} from "@/components/owner-v2/owner-surface-state";
import { TodayDashboard } from "@/components/owner-v2/today-dashboard";
import { ownerDashboardFromDurableProjects } from "@/lib/ownerDashboardLive";
import type { OwnerDashboardTruth } from "@/lib/ownerDashboardLive";
import {
  authorizeOwnerAccessToken,
  ownerAccessCookie,
  OwnerDataError,
  ownerRefreshCookie,
  ownerRestAll,
  ownerRpc,
} from "@/lib/ownerServer";

type Factory = {
  id: string;
  name: string;
  timezone: string;
  verificationLagThresholdMinutes?: number;
};

type DurableProject = {
  id: string;
  name: string;
  client: string;
  status: string;
  target_units: number;
  deadline: string;
  start_at: string;
  shift_calendar: {
    timezone: string;
    shifts: { weekday: number; start: string; end: string }[];
  };
  unit_value_cents: number;
  unit_material_cost_cents: number;
  loaded_labor_rate_cents_per_hour: number;
  target_margin_bps: number | null;
};

type DurableStation = {
  id: string;
  alias: string;
  status: string;
};

type DurableWorker = {
  id: string;
  display_name: string;
};

export default async function TodayPage({
  searchParams,
}: {
  searchParams: Promise<{ factory_id?: string; new?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const cookieStore = await cookies();
  const token = cookieStore.get(ownerAccessCookie)?.value;
  if (!token) redirect("/sign-in");
  let authorization;
  try {
    authorization = await authorizeOwnerAccessToken(token);
  } catch (error) {
    if (
      error instanceof OwnerDataError
      && error.status === 401
      && cookieStore.get(ownerRefreshCookie)?.value
    ) {
      const returnTo = new URLSearchParams();
      if (resolvedSearchParams.factory_id) {
        returnTo.set("factory_id", resolvedSearchParams.factory_id);
      }
      if (resolvedSearchParams.new) returnTo.set("new", resolvedSearchParams.new);
      const ownerPath = returnTo.size ? `/?${returnTo.toString()}` : "/";
      redirect(
        `/api/owner/session?action=refresh&return_to=${encodeURIComponent(ownerPath)}`,
      );
    }
    return <OwnerDataUnavailable />;
  }
  if (!authorization.authorized) {
    if (
      authorization.status === 401
      && cookieStore.get(ownerRefreshCookie)?.value
    ) {
      redirect(
        `/api/owner/session?action=refresh&return_to=${encodeURIComponent("/")}`,
      );
    }
    redirect("/sign-in");
  }

  const factories = authorization.factories as Factory[];
  if (factories.length === 0) return <OwnerNoFactories />;
  const requestedFactoryId = resolvedSearchParams.factory_id;
  if (!requestedFactoryId && factories.length > 1) {
    return <FactoryChooser factories={factories} />;
  }
  const factoryId = requestedFactoryId ?? factories[0]?.id;
  if (!factoryId || !factories.some((factory) => factory.id === factoryId)) {
    return factories.length > 1
      ? <FactoryChooser factories={factories} />
      : <OwnerNoFactories />;
  }

  let projects: DurableProject[];
  let stations: DurableStation[];
  let workers: DurableWorker[];
  let truth: OwnerDashboardTruth;
  const nowIso = new Date().toISOString();
  try {
    [projects, stations, workers] = await Promise.all([
      ownerRestAll<DurableProject>(
        token,
        `owner_projects?${new URLSearchParams({
          factory_id: `eq.${factoryId}`,
          status: "eq.open",
          select:
            "id,name,client,status,target_units,start_at,deadline,shift_calendar,unit_value_cents,unit_material_cost_cents,loaded_labor_rate_cents_per_hour,target_margin_bps",
          order: "deadline.asc,id.asc",
        }).toString()}`,
      ),
      ownerRestAll<DurableStation>(
        token,
        `stations?${new URLSearchParams({
          factory_id: `eq.${factoryId}`,
          select: "id,alias,status",
          order: "alias.asc,id.asc",
        }).toString()}`,
      ),
      ownerRestAll<DurableWorker>(
        token,
        `owner_workers?${new URLSearchParams({
          factory_id: `eq.${factoryId}`,
          status: "eq.active",
          select: "id,display_name",
          order: "display_name.asc,id.asc",
        }).toString()}`,
      ),
    ]);
    truth = await ownerRpc<OwnerDashboardTruth>(
      token,
      "owner_dashboard_truth",
      {
        p_factory_id: factoryId,
        p_now_at: nowIso,
      },
    );
  } catch (error) {
    console.error(
      "Today owner truth fetch failed:",
      error instanceof OwnerDataError
        ? { status: error.status, code: error.publicCode }
        : error,
    );
    return <OwnerDataUnavailable />;
  }

  let data;
  try {
    const factory = factories.find((item) => item.id === factoryId);
    data = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: factory?.timezone ?? "UTC",
      nowIso,
      projects,
      stations,
      verificationLagThresholdMinutes:
        factory?.verificationLagThresholdMinutes ?? 30,
      truth,
    });
  } catch (error) {
    console.error("Today owner truth mapping failed:", error);
    return <OwnerDataUnavailable />;
  }
  return (
    <TodayDashboard
      data={data}
      stationOptions={stations.map((station) => ({
        id: station.id,
        name: station.alias,
        baselineUnitsPerDay: null,
      }))}
      workers={workers.map((worker) => ({
        id: worker.id,
        name: worker.display_name,
      }))}
      initialProjectOpen={resolvedSearchParams.new === "1"}
    />
  );
}
