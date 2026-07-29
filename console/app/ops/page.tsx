import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { OpsCommandCenter } from "@/components/ops/ops-command-center";
import {
  authorizeOpsAccessToken,
  opsAccessCookie,
} from "@/lib/opsServer";

export default async function OpsPage() {
  const accessToken = (await cookies()).get(opsAccessCookie)?.value;
  if (!accessToken) redirect("/ops/sign-in");
  try {
    const authorization = await authorizeOpsAccessToken(accessToken);
    if (!authorization.authorized) redirect("/ops/sign-in");
  } catch {
    redirect("/ops/sign-in");
  }
  return <OpsCommandCenter />;
}
