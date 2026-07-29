import {
  FactoryChooser,
  OwnerDataUnavailable,
  OwnerNoFactories,
} from "@/components/owner-v2/owner-surface-state";
import { WorkforceDirectory } from "@/components/owner-v2/workforce-directory";
import { resolveOwnerPageContext } from "@/lib/ownerPageContext";
import { loadOwnerWorkforceData } from "@/lib/ownerStationServer";

export default async function WorkforcePage({
  searchParams,
}: {
  searchParams: Promise<{ factory_id?: string }>;
}) {
  const params = await searchParams;
  const returnTo = params.factory_id
    ? `/workforce?factory_id=${encodeURIComponent(params.factory_id)}`
    : "/workforce";
  const context = await resolveOwnerPageContext({
    requestedFactoryId: params.factory_id,
    returnTo,
  });
  if (context.kind === "unavailable") return <OwnerDataUnavailable />;
  if (context.kind === "none") return <OwnerNoFactories />;
  if (context.kind === "choose") {
    return <FactoryChooser factories={context.factories} basePath="/workforce" />;
  }
  let data;
  try {
    data = await loadOwnerWorkforceData({
      accessToken: context.accessToken,
      factoryId: context.factory.id,
      timezone: context.factory.timezone,
    });
  } catch {
    return <OwnerDataUnavailable />;
  }
  return <WorkforceDirectory data={data} />;
}
