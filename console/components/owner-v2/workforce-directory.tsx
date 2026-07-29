"use client";

import {
  BadgeCheck,
  Plus,
  Save,
  UserRound,
  Users,
  Workflow,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useOwnerSurfaceStatus } from "@/components/owner-v2/owner-shell";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ownerApiFetch } from "@/lib/ownerClient";
import type { OwnerWorkforceData } from "@/lib/ownerStationTypes";

const panel =
  "overflow-hidden rounded-[8px] border border-border bg-panel-2";

export function WorkforceDirectory({
  data,
  preview = false,
}: {
  data: OwnerWorkforceData;
  preview?: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [employeeCode, setEmployeeCode] = useState("");
  const [primaryRole, setPrimaryRole] = useState("");
  useOwnerSurfaceStatus("connected");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (!displayName.trim()) {
      setMessage("Enter the worker's name.");
      return;
    }
    if (preview) {
      setMessage("Preview data only. No worker was added.");
      return;
    }
    setBusy(true);
    try {
      const response = await ownerApiFetch(
        `/api/owner/workers?factory_id=${encodeURIComponent(data.factoryId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            displayName: displayName.trim(),
            employeeCode: employeeCode.trim(),
            primaryRole: primaryRole.trim(),
          }),
        },
      );
      if (response.ok) {
        setDisplayName("");
        setEmployeeCode("");
        setPrimaryRole("");
        setOpen(false);
        router.refresh();
        return;
      }
      const payload = (await response.json().catch(() => null)) as {
        error?: string;
      } | null;
      setMessage(
        payload?.error === "OWNER_RETRY_REQUIRED"
          ? "Your session was refreshed. Review the name and submit again."
          : payload?.error === "OWNER_CONFLICT"
            ? "That employee code is already in use."
            : "Worker could not be added. Your entries are unchanged.",
      );
    } catch {
      setMessage("Worker could not be added. Your entries are unchanged.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-owner-workforce className="space-y-3">
      <div className="flex min-h-[60px] items-center justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase text-text-mut">People & assignments</p>
          <h1 className="mt-1 text-xl font-semibold">Workforce</h1>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex h-11 items-center gap-2 rounded-[7px] bg-accent px-5 text-sm font-semibold text-black hover:bg-accent-hi"
        >
          <Plus size={17} aria-hidden="true" />
          Worker
        </button>
      </div>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Workforce summary">
        <WorkforceKpi
          label="Active employees"
          value={data.activeCount}
          icon={Users}
        />
        <WorkforceKpi
          label="Assigned this shift"
          value={data.assignedCount}
          icon={BadgeCheck}
        />
        <WorkforceKpi
          label="Stations staffed"
          value={data.stationCount}
          icon={Workflow}
        />
      </section>

      <section className={panel}>
        <div className="flex min-h-[48px] items-center border-b border-border px-4">
          <h2 className="text-[11px] font-medium uppercase text-text-mut">
            Employee directory
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] border-collapse text-left text-xs">
            <thead className="text-text-mut">
              <tr className="h-10 border-b border-border">
                <th className="px-4 font-normal">Employee</th>
                <th className="px-3 font-normal">Employee ID</th>
                <th className="px-3 font-normal">Status</th>
                <th className="px-3 font-normal">Primary role</th>
                <th className="px-3 font-normal">Current assignment</th>
                <th className="px-3 font-normal">Scheduled interval</th>
                <th className="px-3 font-normal">Attribution</th>
              </tr>
            </thead>
            <tbody>
              {data.members.length ? (
                data.members.map((member) => (
                  <tr key={member.id} className="min-h-[58px] border-b border-border last:border-b-0">
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-3 font-medium">
                        <span className="grid size-8 place-items-center rounded-full border border-border text-text-mut">
                          <UserRound size={15} aria-hidden="true" />
                        </span>
                        {member.name}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-text-mut">
                      {member.employeeCode ?? "Not assigned"}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={
                          member.status === "active" ? "text-good" : "text-text-dim"
                        }
                      >
                        {member.status === "active" ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-text-mut">
                      {member.primaryRole ?? "Not recorded"}
                    </td>
                    <td className="px-3 py-3">
                      {member.stationName ? (
                        <>
                          <span className="block">{member.stationName}</span>
                          <span className="mt-0.5 block text-[11px] text-text-mut">
                            {member.projectName}
                          </span>
                        </>
                      ) : (
                        <span className="text-text-dim">Unassigned</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-text-mut">
                      {member.scheduledInterval ?? "No interval"}
                    </td>
                    <td className="px-3 py-3">
                      {member.attribution === "solo_high_confidence" ? (
                        <span className="text-good">Solo interval · high confidence</span>
                      ) : member.attribution === "team_only" ? (
                        <span className="text-warn">Team contribution only</span>
                      ) : (
                        <span className="text-text-dim">No attribution</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="h-36 px-4 text-center text-text-mut">
                    No employees have been added to this factory.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="border-t border-border px-4 py-3 text-xs text-text-mut">
          Workforce records show assignments, not rankings. Output remains
          attributed to the station team unless a solo checked-in interval has
          sufficient coverage.
        </p>
      </section>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="max-w-[440px] bg-bg">
          <SheetHeader className="border-b border-border px-6 pb-5 pt-6">
            <SheetTitle>Add employee</SheetTitle>
            <SheetDescription>
              Create the worker record used for project and station assignments.
            </SheetDescription>
          </SheetHeader>
          <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-5 px-6 py-6">
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-mut">
                  Full name
                </span>
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  maxLength={200}
                  autoComplete="off"
                  className="h-11 w-full border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-mut">
                  Primary role (optional)
                </span>
                <input
                  value={primaryRole}
                  onChange={(event) => setPrimaryRole(event.target.value)}
                  maxLength={100}
                  autoComplete="off"
                  className="h-11 w-full border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-mut">
                  Employee ID (optional)
                </span>
                <input
                  value={employeeCode}
                  onChange={(event) => setEmployeeCode(event.target.value)}
                  maxLength={100}
                  autoComplete="off"
                  className="h-11 w-full border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent"
                />
              </label>
              {message ? (
                <p role="alert" className="text-sm text-warn">
                  {message}
                </p>
              ) : null}
            </div>
            <div className="flex justify-end border-t border-border px-6 py-4">
              <button
                type="submit"
                disabled={busy}
                className="inline-flex h-11 items-center gap-2 rounded-[7px] bg-accent px-5 text-sm font-semibold text-black hover:bg-accent-hi disabled:opacity-60"
              >
                <Save size={16} aria-hidden="true" />
                Add employee
              </button>
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function WorkforceKpi({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Users;
}) {
  return (
    <article className={`${panel} min-h-[112px] px-4 py-4`}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase text-text-mut">{label}</p>
        <Icon size={18} className="text-accent" aria-hidden="true" />
      </div>
      <p className="mt-4 text-3xl font-semibold">{value}</p>
    </article>
  );
}
