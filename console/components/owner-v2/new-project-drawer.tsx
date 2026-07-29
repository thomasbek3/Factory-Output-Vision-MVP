"use client";

import { Temporal } from "@js-temporal/polyfill";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  CircleHelp,
  Play,
  Save,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { evaluateProjectFeasibility } from "@/lib/ownerEconomics";
import {
  normalizeOwnerProjectDraft,
  ownerProjectRpcPayload,
  type OwnerProjectValidation,
  validateOwnerProjectDraft,
} from "@/lib/ownerProjectForm";
import {
  mergeOwnerProjectFormState,
  type OwnerProjectFormState,
} from "@/lib/ownerProjectClientState";
import { ownerApiFetch } from "@/lib/ownerClient";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type StationOption = {
  id: string;
  name: string;
  baselineUnitsPerDay: number | null;
};

type WorkerOption = {
  id: string;
  name: string;
};

type FormState = OwnerProjectFormState;

type StationSuggestion = {
  stationId: string;
  confidencePercent: number;
};

const fields =
  "h-11 w-full border border-border bg-panel-2 px-3 text-sm text-text outline-none focus:border-accent md:h-10";

function initialForm(
  nowIso: string,
  timezone: string,
  workers: WorkerOption[],
  preview: boolean,
  stationSuggestion: StationSuggestion | null,
): FormState {
  const date = Temporal.Instant.from(nowIso)
    .toZonedDateTimeISO(timezone)
    .toPlainDate();
  return {
    name: preview ? "Harbor Fence Batch" : "",
    client: preview ? "Harbor Contracting" : "",
    targetUnits: preview ? "400" : "",
    valueMode: "per_unit",
    valueUsd: preview ? "28.00" : "",
    materialMode: "per_unit",
    materialUsd: preview ? "12.25" : "",
    stationId: stationSuggestion?.stationId ?? "",
    stationSuggested: stationSuggestion !== null,
    stationConfirmed: false,
    projectStartDate: date.toString(),
    projectStartTime: "07:00",
    deadlineDate: date.add({ days: 3 }).toString(),
    deadlineTime: "17:00",
    shiftStartTime: "07:00",
    shiftEndTime: "16:30",
    shiftDays: [1, 2, 3, 4, 5],
    workerIds: preview ? workers.map((worker) => worker.id) : [],
    loadedLaborRateUsd: preview ? "24.00" : "",
    targetMarginPercent: preview ? "20" : "",
  };
}

function formPayload(
  state: FormState,
  factoryId: string,
  timezone: string,
) {
  return {
    ...state,
    factoryId,
    timezone,
    shiftCalendar: {
      timezone,
      shifts: state.shiftDays.map((weekday) => ({
        weekday,
        start: state.shiftStartTime,
        end: state.shiftEndTime,
      })),
    },
    startDate: state.projectStartDate,
    startTime: state.projectStartTime,
  };
}

export function NewProjectDrawer({
  open,
  onOpenChange,
  factoryId,
  timezone,
  nowIso,
  stations,
  workers,
  preview = false,
  stationSuggestion = null,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  factoryId: string;
  timezone: string;
  nowIso: string;
  stations: StationOption[];
  workers: WorkerOption[];
  preview?: boolean;
  stationSuggestion?: StationSuggestion | null;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [form, setForm] = useState(() =>
    initialForm(
      nowIso,
      timezone,
      workers,
      preview,
      stationSuggestion,
    ),
  );
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [attemptedSteps, setAttemptedSteps] = useState({
    1: false,
    2: false,
    3: false,
  });
  const dirtyRef = useRef(false);
  const loadedFactoryRef = useRef<string | null>(null);
  const initialFormRef = useRef(form);

  useEffect(() => {
    if (
      !open
      || preview
      || loadedFactoryRef.current === factoryId
    ) {
      return;
    }
    loadedFactoryRef.current = factoryId;
    let cancelled = false;
    const storageKey = `fv-owner-project-draft:${factoryId}`;
    try {
      const resumed = window.sessionStorage.getItem(storageKey);
      if (resumed) {
        setForm(
          mergeOwnerProjectFormState(
            JSON.parse(resumed) as unknown,
            initialFormRef.current,
          ),
        );
        dirtyRef.current = true;
      }
    } catch {
      window.sessionStorage.removeItem(storageKey);
    }
    void ownerApiFetch(
      `/api/owner/project-draft?factory_id=${encodeURIComponent(factoryId)}`,
    )
      .then(async (response) => {
        if (!response.ok) return null;
        return (await response.json()) as { draft?: unknown };
      })
      .then((result) => {
        if (!cancelled && result?.draft && !dirtyRef.current) {
          setForm((current) =>
            mergeOwnerProjectFormState(result.draft, current),
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessage("Saved draft could not be loaded. Your entries are unchanged.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [factoryId, open, preview]);

  const payload = useMemo(
    () => formPayload(form, factoryId, timezone),
    [factoryId, form, timezone],
  );
  const draft = useMemo(
    () => normalizeOwnerProjectDraft(payload),
    [payload],
  );
  const validation = useMemo(
    () => validateOwnerProjectDraft(draft),
    [draft],
  );
  const selectedStation = stations.find(
    (station) => station.id === form.stationId,
  );
  const economics = useMemo(() => {
    if (!validation.ok || draft.targetUnits === null) return null;
    try {
      const rpc = ownerProjectRpcPayload(draft, "open");
      const productionValue =
        draft.targetUnits * (draft.unitValueCents ?? 0);
      const materialCost =
        draft.targetUnits * (draft.unitMaterialCostCents ?? 0);
      const margin =
        productionValue
        - materialCost
        - rpc.p_planned_direct_labor_cents;
      const baseline = selectedStation?.baselineUnitsPerDay ?? null;
      const feasibility = evaluateProjectFeasibility({
        targetUnits: draft.targetUnits,
        startIso: rpc.p_start_at,
        deadlineIso: rpc.p_deadline,
        calendar: draft.shiftCalendar as {
          timezone: string;
          shifts: { weekday: number; start: string; end: string }[];
        },
        baselineUnitsPerDay: baseline,
      });
      return {
        plannedMarginCents:
          draft.loadedLaborRateCentsPerHour === null ? null : margin,
        marginBps:
          draft.loadedLaborRateCentsPerHour !== null && productionValue > 0
            ? Math.round((margin * 10_000) / productionValue)
            : null,
        targetMarginBps: draft.targetMarginBps,
        requiredUnitsPerDay:
          feasibility.requiredUnitsPerDay === null
            ? null
            : Math.ceil(feasibility.requiredUnitsPerDay),
        requiredUnitsPerHour:
          feasibility.requiredUnitsPerHour === null
            ? null
            : Math.ceil(feasibility.requiredUnitsPerHour * 10) / 10,
        baseline,
        feasibility: feasibility.status,
      };
    } catch {
      return null;
    }
  }, [draft, selectedStation, validation.ok]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    dirtyRef.current = true;
  }

  function next() {
    setAttemptedSteps((current) => ({ ...current, [step]: true }));
    if (step === 1 && !validation.steps.what) {
      setMessage("Review the highlighted project details.");
      return;
    }
    if (step === 2 && !validation.steps.whereWhen) {
      setMessage("Review the highlighted station and schedule fields.");
      return;
    }
    setStep((current) => (current === 1 ? 2 : 3));
    setMessage("");
  }

  async function saveDraft() {
    if (preview) {
      setMessage("Preview data only. No draft was saved.");
      return;
    }
    setBusy(true);
    try {
      const response = await ownerApiFetch(
        `/api/owner/project-draft?factory_id=${encodeURIComponent(factoryId)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        },
      );
      setMessage(response.ok ? "Draft saved." : "Draft could not be saved.");
      if (response.ok) {
        window.sessionStorage.removeItem(`fv-owner-project-draft:${factoryId}`);
        dirtyRef.current = false;
      }
    } catch {
      setMessage("Draft could not be saved. Your entries are still here.");
    } finally {
      setBusy(false);
    }
  }

  async function startProject() {
    if (preview) {
      setMessage("Preview data only. No project was created.");
      return;
    }
    if (!validation.ok) {
      setAttemptedSteps({ 1: true, 2: true, 3: true });
      setMessage("Complete all three steps before starting the project.");
      return;
    }
    setBusy(true);
    try {
      const response = await ownerApiFetch(
        `/api/owner/projects?factory_id=${encodeURIComponent(factoryId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (response.ok) {
        window.sessionStorage.removeItem(`fv-owner-project-draft:${factoryId}`);
        window.location.assign(`/?factory_id=${encodeURIComponent(factoryId)}`);
        return;
      }
      const result = (await response.json().catch(() => null)) as {
        error?: string;
      } | null;
      if (result?.error === "OWNER_RETRY_REQUIRED") {
        setMessage(
          "Your session was refreshed. Review the plan, then press Start project again.",
        );
        return;
      }
      if (
        response.status === 401
        || result?.error === "OWNER_REAUTH_REQUIRED"
        || result?.error === "OWNER_AUTH_REQUIRED"
      ) {
        window.sessionStorage.setItem(
          `fv-owner-project-draft:${factoryId}`,
          JSON.stringify(form),
        );
        const returnTo = `/?factory_id=${encodeURIComponent(factoryId)}&new=1`;
        window.location.assign(
          `/sign-in?return_to=${encodeURIComponent(returnTo)}`,
        );
        return;
      }
      setMessage(
        result?.error === "OWNER_CONFLICT"
          ? "That station or worker is already assigned during this time."
          : "Project could not be started. Your entries are unchanged.",
      );
    } catch {
      setMessage("Project could not be started. Your entries are unchanged.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        id="new-project-drawer"
        className="max-w-[640px] bg-bg shadow-2xl"
        data-testid="new-project-drawer"
      >
        <SheetHeader className="border-b border-border px-6 pb-5 pt-6">
          <SheetTitle className="text-xl">New production project</SheetTitle>
          <SheetDescription className="sr-only">
            Configure what will be produced, where and when it will run, and
            the assigned labor and margin goal.
          </SheetDescription>
          <div
            className="mt-5 grid grid-cols-3"
            role="group"
            aria-label={`Project setup, step ${step} of 3`}
          >
            {(["What", "Where & when", "Labor & goal"] as const).map(
              (label, index) => {
                const number = (index + 1) as 1 | 2 | 3;
                const complete = number < step;
                const active = number === step;
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setStep(number)}
                    disabled={
                      (number === 2 && !validation.steps.what)
                      || (
                        number === 3
                        && (
                          !validation.steps.what
                          || !validation.steps.whereWhen
                        )
                      )
                    }
                    aria-current={active ? "step" : undefined}
                    className="relative flex flex-col items-center gap-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {index ? (
                      <span className="absolute right-1/2 top-4 h-px w-full bg-border" />
                    ) : null}
                    <span
                      className={`relative z-10 grid size-8 place-items-center rounded-full border ${
                        active
                          ? "border-accent bg-accent text-black"
                          : complete
                            ? "border-good/40 bg-panel text-good"
                            : "border-border bg-panel text-text-mut"
                      }`}
                    >
                      {complete ? <Check size={15} /> : number}
                    </span>
                    <span className={active ? "text-text" : "text-text-mut"}>
                      {label}
                    </span>
                  </button>
                );
              },
            )}
          </div>
        </SheetHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          <div className={step === 3 ? "grid gap-5 md:grid-cols-[184px_1fr]" : ""}>
            {step === 3 ? (
              <div className="space-y-3">
                <StepSummary
                  number={1}
                  title="What"
                  onEdit={() => setStep(1)}
                  rows={[
                    ["Project", form.name || "Not set"],
                    ["Customer", form.client || "Not set"],
                    ["Target", `${form.targetUnits || "0"} units`],
                    ["Value per unit", `$${form.valueUsd || "0.00"}`],
                    ["Material per unit", `$${form.materialUsd || "0.00"}`],
                  ]}
                />
                <StepSummary
                  number={2}
                  title="Where & when"
                  onEdit={() => setStep(2)}
                  rows={[
                    ["Station", selectedStation?.name ?? "Not set"],
                    [
                      "Start",
                      `${form.projectStartDate} ${form.projectStartTime}`,
                    ],
                    ["Deadline", `${form.deadlineDate} ${form.deadlineTime}`],
                    [
                      "Shift",
                      `${form.shiftStartTime}–${form.shiftEndTime}`,
                    ],
                  ]}
                />
              </div>
            ) : null}

            <div>
              {step === 1 ? (
                <StepOne
                  form={form}
                  update={update}
                  errors={attemptedSteps[1] ? validation.errors : {}}
                />
              ) : step === 2 ? (
                <StepTwo
                  form={form}
                  update={update}
                  stations={stations}
                  stationSuggestion={stationSuggestion}
                  errors={attemptedSteps[2] ? validation.errors : {}}
                />
              ) : (
                <StepThree
                  form={form}
                  update={update}
                  workers={workers}
                  economics={economics}
                  errors={attemptedSteps[3] ? validation.errors : {}}
                />
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-border bg-bg px-6 py-4">
          {message ? (
            <p className="mb-3 text-sm text-warn" role="alert">
              {message}
            </p>
          ) : null}
          <div className="flex items-center justify-between gap-3">
            <div>
              {step > 1 ? (
                <button
                  type="button"
                  onClick={() => setStep(step === 3 ? 2 : 1)}
                  className="inline-flex h-11 items-center gap-2 px-2 text-sm text-text-mut hover:text-text"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
              ) : null}
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => void saveDraft()}
                disabled={busy}
                className="inline-flex h-11 items-center gap-2 rounded-[4px] border border-border px-5 text-sm font-semibold hover:bg-panel disabled:cursor-wait disabled:opacity-60"
              >
                <Save size={16} />
                Save draft
              </button>
              {step < 3 ? (
                <button
                  type="button"
                  onClick={next}
                  className="inline-flex h-11 items-center gap-2 rounded-[7px] bg-accent px-6 text-sm font-semibold text-black hover:bg-accent-hi"
                >
                  Continue
                  <ChevronRight size={16} />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void startProject()}
                  disabled={busy}
                  className="inline-flex h-11 items-center gap-2 rounded-[7px] bg-accent px-6 text-sm font-semibold text-black hover:bg-accent-hi disabled:opacity-60"
                >
                  <Play size={16} />
                  Start project
                </button>
              )}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function StepOne({
  form,
  update,
  errors,
}: {
  form: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  errors: OwnerProjectValidation["errors"];
}) {
  return (
    <div>
      <StepHeading number={1} title="What are you producing?" />
      <div className="mt-6 grid gap-4">
        <Field
          label="Project name"
          htmlFor="project-name"
          error={errors.name}
        >
          <input
            id="project-name"
            className={fields}
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? "project-name-error" : undefined}
            autoFocus
          />
        </Field>
        <Field
          label="Customer"
          htmlFor="project-customer"
          error={errors.client}
        >
          <input
            id="project-customer"
            className={fields}
            value={form.client}
            onChange={(event) => update("client", event.target.value)}
            aria-invalid={Boolean(errors.client)}
            aria-describedby={
              errors.client ? "project-customer-error" : undefined
            }
          />
        </Field>
        <Field
          label="Target units"
          htmlFor="project-target"
          error={errors.targetUnits}
        >
          <input
            id="project-target"
            className={fields}
            inputMode="numeric"
            value={form.targetUnits}
            onChange={(event) => update("targetUnits", event.target.value)}
            aria-invalid={Boolean(errors.targetUnits)}
            aria-describedby={
              errors.targetUnits ? "project-target-error" : undefined
            }
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Value per unit"
            htmlFor="project-value"
            error={errors.unitValueCents}
          >
            <MoneyInput
              id="project-value"
              value={form.valueUsd}
              onChange={(value) => update("valueUsd", value)}
              error={errors.unitValueCents}
            />
          </Field>
          <Field
            label="Material cost per unit"
            htmlFor="project-material"
            error={errors.unitMaterialCostCents}
          >
            <MoneyInput
              id="project-material"
              value={form.materialUsd}
              onChange={(value) => update("materialUsd", value)}
              error={errors.unitMaterialCostCents}
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

function StepTwo({
  form,
  update,
  stations,
  stationSuggestion,
  errors,
}: {
  form: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  stations: StationOption[];
  stationSuggestion: StationSuggestion | null;
  errors: OwnerProjectValidation["errors"];
}) {
  return (
    <div>
      <StepHeading number={2} title="Where and when?" />
      <div className="mt-6 grid gap-4">
        <Field
          label="Station"
          htmlFor="project-station"
          error={errors.stationId ?? errors.stationConfirmed}
        >
          <select
            id="project-station"
            className={fields}
            value={form.stationId}
            onChange={(event) => {
              update("stationId", event.target.value);
              update("stationSuggested", false);
              update("stationConfirmed", true);
            }}
            aria-invalid={Boolean(errors.stationId ?? errors.stationConfirmed)}
            aria-describedby={
              errors.stationId || errors.stationConfirmed
                ? "project-station-error"
                : undefined
            }
          >
            <option value="">Select a station</option>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>
                {station.name}
              </option>
            ))}
          </select>
        </Field>
        {form.stationSuggested ? (
          <label className="flex items-start gap-3 border border-accent/40 bg-accent-tint p-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 accent-[var(--accent)]"
              checked={form.stationConfirmed}
              onChange={(event) =>
                update("stationConfirmed", event.target.checked)
              }
            />
            <span>
              <strong className="block text-text">Confirm suggested station</strong>
              <span className="text-text-mut">
                Suggested from recent camera activity
                {stationSuggestion
                  ? ` · ${stationSuggestion.confidencePercent}% confidence`
                  : ""}
                . Choose another station above to change it.
              </span>
            </span>
          </label>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Start date"
            htmlFor="project-start-date"
            error={errors.start}
          >
            <input
              id="project-start-date"
              type="date"
              className={fields}
              value={form.projectStartDate}
              onChange={(event) =>
                update("projectStartDate", event.target.value)
              }
              aria-invalid={Boolean(errors.start)}
              aria-describedby={
                errors.start ? "project-start-date-error" : undefined
              }
            />
          </Field>
          <Field
            label="Start time"
            htmlFor="project-start-time"
            error={errors.start}
          >
            <input
              id="project-start-time"
              type="time"
              className={fields}
              value={form.projectStartTime}
              onChange={(event) =>
                update("projectStartTime", event.target.value)
              }
              aria-invalid={Boolean(errors.start)}
              aria-describedby={
                errors.start ? "project-start-time-error" : undefined
              }
            />
          </Field>
          <Field
            label="Deadline date"
            htmlFor="project-deadline-date"
            error={errors.deadline}
          >
            <input
              id="project-deadline-date"
              type="date"
              className={fields}
              value={form.deadlineDate}
              onChange={(event) => update("deadlineDate", event.target.value)}
              aria-invalid={Boolean(errors.deadline)}
              aria-describedby={
                errors.deadline ? "project-deadline-date-error" : undefined
              }
            />
          </Field>
          <Field
            label="Deadline time"
            htmlFor="project-deadline-time"
            error={errors.deadline}
          >
            <input
              id="project-deadline-time"
              type="time"
              className={fields}
              value={form.deadlineTime}
              onChange={(event) => update("deadlineTime", event.target.value)}
              aria-invalid={Boolean(errors.deadline)}
              aria-describedby={
                errors.deadline ? "project-deadline-time-error" : undefined
              }
            />
          </Field>
        </div>
        <FieldGroup
          label="Daily shift"
          error={errors.shiftCalendar}
          errorId="project-shift-error"
        >
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
            <input
              type="time"
              className={fields}
              aria-label="Daily shift start"
              value={form.shiftStartTime}
              onChange={(event) => update("shiftStartTime", event.target.value)}
              aria-invalid={Boolean(errors.shiftCalendar)}
              aria-describedby={
                errors.shiftCalendar ? "project-shift-error" : undefined
              }
            />
            <span className="text-text-dim">to</span>
            <input
              type="time"
              className={fields}
              value={form.shiftEndTime}
              onChange={(event) => update("shiftEndTime", event.target.value)}
              aria-label="Daily shift end"
              aria-invalid={Boolean(errors.shiftCalendar)}
              aria-describedby={
                errors.shiftCalendar ? "project-shift-error" : undefined
              }
            />
          </div>
        </FieldGroup>
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-text-mut">
            Working days
          </legend>
          <div className="grid grid-cols-7 gap-1">
            {["M", "T", "W", "T", "F", "S", "S"].map((label, index) => {
              const day = index + 1;
              const selected = form.shiftDays.includes(day);
              return (
                <button
                  key={`${label}-${day}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() =>
                    update(
                      "shiftDays",
                      selected
                        ? form.shiftDays.filter((value) => value !== day)
                        : [...form.shiftDays, day].sort(
                            (left, right) => left - right,
                          ),
                    )
                  }
                  className={`h-11 border text-xs md:h-9 ${
                    selected
                      ? "border-accent bg-accent-tint text-accent"
                      : "border-border text-text-mut"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </fieldset>
      </div>
    </div>
  );
}

function StepThree({
  form,
  update,
  workers,
  economics,
  errors,
}: {
  form: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  workers: WorkerOption[];
  economics: {
    plannedMarginCents: number | null;
    marginBps: number | null;
    targetMarginBps: number | null;
    requiredUnitsPerDay: number | null;
    requiredUnitsPerHour: number | null;
    baseline: number | null;
    feasibility: string;
  } | null;
  errors: OwnerProjectValidation["errors"];
}) {
  return (
    <div>
      <StepHeading number={3} title="Labor & goal" />
      <p className="mt-2 text-sm leading-5 text-text-mut">
        Confirm how this work will run and whether the plan is feasible.
      </p>
      <div className="mt-6 grid gap-4">
        <FieldGroup
          label="Assigned team"
          error={errors.workerIds}
          errorId="project-team-error"
        >
          <div className="border border-border bg-panel-2">
            {workers.length ? (
              workers.map((worker) => {
                const selected = form.workerIds.includes(worker.id);
                return (
                  <label
                    key={worker.id}
                    className="flex min-h-11 items-center gap-3 border-b border-border px-3 last:border-b-0"
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      aria-describedby={
                        errors.workerIds ? "project-team-error" : undefined
                      }
                      onChange={() =>
                        update(
                          "workerIds",
                          selected
                            ? form.workerIds.filter((id) => id !== worker.id)
                            : [...form.workerIds, worker.id],
                        )
                      }
                    />
                    <span className="text-sm">{worker.name}</span>
                  </label>
                );
              })
            ) : (
              <p className="p-3 text-sm text-text-mut">
                Add workers in Workforce before starting a project.
              </p>
            )}
          </div>
        </FieldGroup>
        <Field
          label="Loaded labor rate (optional)"
          htmlFor="project-labor-rate"
          help="Hourly wage plus employer taxes and direct labor burden."
          error={errors.loadedLaborRateCentsPerHour}
        >
          <div className="relative">
            <span className="absolute left-3 top-2.5 text-sm text-text-mut">$</span>
            <input
              id="project-labor-rate"
              className={`${fields} pl-7 pr-14`}
              inputMode="decimal"
              value={form.loadedLaborRateUsd}
              onChange={(event) =>
                update("loadedLaborRateUsd", event.target.value)
              }
              aria-invalid={Boolean(errors.loadedLaborRateCentsPerHour)}
              aria-describedby={
                errors.loadedLaborRateCentsPerHour
                  ? "project-labor-rate-error"
                  : undefined
              }
            />
            <span className="absolute right-3 top-2.5 text-sm text-text-mut">
              /hour
            </span>
          </div>
        </Field>
        <Field
          label="Target margin (optional)"
          htmlFor="project-target-margin"
          error={errors.targetMarginBps}
        >
          <div className="relative">
            <input
              id="project-target-margin"
              className={`${fields} pr-8`}
              inputMode="decimal"
              value={form.targetMarginPercent}
              onChange={(event) =>
                update("targetMarginPercent", event.target.value)
              }
              aria-invalid={Boolean(errors.targetMarginBps)}
              aria-describedby={
                errors.targetMarginBps
                  ? "project-target-margin-error"
                  : undefined
              }
            />
            <span className="absolute right-3 top-2.5 text-sm text-text-mut">%</span>
          </div>
        </Field>
      </div>

      <div className="mt-6 border border-border bg-panel-2">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="font-semibold">Feasibility check</h3>
          <span
            className={`text-sm font-medium ${
              economics?.feasibility === "Feasible"
                ? "text-good"
                : economics?.feasibility === "Not feasible"
                  ? "text-bad"
                  : economics?.feasibility === "Tight"
                    ? "text-warn"
                    : "text-text-dim"
            }`}
          >
            {economics?.feasibility ?? "Complete all fields"}
          </span>
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div>
            <p className="text-xs text-text-mut">Required pace</p>
            <p className="mt-1 text-lg font-semibold">
              {economics
                ? economics.requiredUnitsPerDay === null
                  ? "Unavailable"
                  : `${economics.requiredUnitsPerDay} units/day`
                : "Unavailable"}
            </p>
            {economics?.requiredUnitsPerHour !== null && economics ? (
              <p className="mt-1 text-xs text-text-mut">
                {economics.requiredUnitsPerHour} units/hour during scheduled
                shifts
              </p>
            ) : null}
            <p className="mt-2 text-xs text-text-dim">
              {economics?.baseline === null || !economics
                ? "Station baseline unavailable"
                : `Station averages ${economics.baseline}/day`}
            </p>
          </div>
          <div className="border-t border-border pt-4 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
            <p className="text-xs text-text-mut">
              Planned margin after direct costs
            </p>
            <p
              className={`mt-1 text-2xl font-semibold ${
                economics?.plannedMarginCents === null || !economics
                  ? "text-text-dim"
                  : economics.plannedMarginCents < 0
                    ? "text-bad"
                    : economics.targetMarginBps !== null
                        && economics.marginBps !== null
                        && economics.marginBps < economics.targetMarginBps
                      ? "text-warn"
                      : "text-good"
              }`}
            >
              {economics?.plannedMarginCents !== null && economics
                ? new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                    maximumFractionDigits: 0,
                  }).format(economics.plannedMarginCents / 100)
                : "Unavailable"}
              {economics?.marginBps !== null && economics ? (
                <span className="ml-2 text-sm font-normal text-text-mut">
                  · {(economics.marginBps / 100).toFixed(1)}%
                </span>
              ) : null}
            </p>
            {economics?.plannedMarginCents === null ? (
              <p className="mt-1 text-xs text-text-dim">
                Add a loaded labor rate to compare output with labor expense.
              </p>
            ) : null}
            {economics?.targetMarginBps !== null && economics ? (
              <p className="mt-1 text-xs text-text-dim">
                Target {(economics.targetMarginBps / 100).toFixed(1)}%
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepHeading({ number, title }: { number: number; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-7 place-items-center rounded-full bg-accent text-sm font-semibold text-black">
        {number}
      </span>
      <h2 className="text-lg font-semibold">{title}</h2>
    </div>
  );
}

function StepSummary({
  number,
  title,
  rows,
  onEdit,
}: {
  number: number;
  title: string;
  rows: [string, string][];
  onEdit: () => void;
}) {
  return (
    <section className="border border-border bg-panel-2 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-text-mut">
          <span className="mr-2 inline-grid size-5 place-items-center rounded-full bg-idle text-[10px] text-text">
            {number}
          </span>
          {title}
        </p>
        <button
          type="button"
          onClick={onEdit}
          className="min-h-11 min-w-11 text-xs text-text-mut underline hover:text-text md:min-h-0 md:min-w-0"
        >
          Edit
        </button>
      </div>
      <dl className="mt-3 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[11px] text-text-dim">{label}</dt>
            <dd className="truncate text-xs text-text">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Field({
  label,
  htmlFor,
  help,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  help?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="block">
      <label
        htmlFor={htmlFor}
        className="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-mut"
      >
        {label}
        {help ? (
          <button
            type="button"
            title={help}
            aria-label={help}
            className="-my-3 inline-grid size-11 place-items-center text-text-dim hover:text-text md:-my-2 md:size-9"
          >
            <CircleHelp size={13} aria-hidden="true" />
          </button>
        ) : null}
      </label>
      {children}
      {error ? (
        <p
          id={`${htmlFor}-error`}
          className="mt-1.5 text-xs text-bad"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

function FieldGroup({
  label,
  error,
  errorId,
  children,
}: {
  label: string;
  error?: string;
  errorId: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-xs font-medium text-text-mut">
        {label}
      </legend>
      {children}
      {error ? (
        <p id={errorId} className="mt-1.5 text-xs text-bad">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

function MoneyInput({
  id,
  value,
  onChange,
  error,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <div className="relative">
      <span className="absolute left-3 top-2.5 text-sm text-text-mut">$</span>
      <input
        id={id}
        className={`${fields} pl-7`}
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
      />
    </div>
  );
}
