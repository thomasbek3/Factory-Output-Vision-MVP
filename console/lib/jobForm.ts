export type NewJobInput = {
  client: string;
  title: string;
  units_required: number;
  quote_usd: number;
  cogs_usd: number;
  labor_budget_usd: number;
  deadline: string;
  station_ids: string[];
};

export type NewJobValidation = {
  ok: boolean;
  errors: Partial<Record<keyof NewJobInput, string>>;
};

export function validateNewJobInput(input: NewJobInput): NewJobValidation {
  const errors: NewJobValidation["errors"] = {};

  if (!input.client.trim()) errors.client = "Client is required.";
  if (!input.title.trim()) errors.title = "Title is required.";
  if (!Number.isFinite(input.units_required) || input.units_required <= 0) {
    errors.units_required = "Units required must be greater than 0.";
  }
  if (!Number.isFinite(input.quote_usd) || input.quote_usd <= 0) {
    errors.quote_usd = "Quote must be greater than 0.";
  }
  if (!Number.isFinite(input.cogs_usd) || input.cogs_usd <= 0) {
    errors.cogs_usd = "COGS must be greater than 0.";
  }
  if (!Number.isFinite(input.labor_budget_usd) || input.labor_budget_usd <= 0) {
    errors.labor_budget_usd = "Labor budget must be greater than 0.";
  }
  if (!input.deadline || Number.isNaN(new Date(input.deadline).getTime())) {
    errors.deadline = "Deadline is required.";
  }
  if (!input.station_ids.length) errors.station_ids = "Pick at least one station.";

  return { ok: Object.keys(errors).length === 0, errors };
}
