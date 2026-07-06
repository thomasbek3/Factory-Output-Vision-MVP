"use client";

import { useCallback, useEffect, useState } from "react";
import { jobs as seedJobs, type JobSeed } from "@/lib/demoData";
import type { NewJobInput } from "@/lib/jobForm";

type JobsResponse = {
  jobs: JobSeed[];
};

type JobResponse = {
  job: JobSeed;
};

function replaceJob(jobs: JobSeed[], next: JobSeed) {
  return jobs.map((job) => (job.id === next.id ? next : job));
}

export function useConsoleJobs() {
  const [jobs, setJobs] = useState<JobSeed[]>(seedJobs);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/jobs", { cache: "no-store" });
      if (!response.ok) throw new Error(`Jobs API returned ${response.status}`);
      const payload = (await response.json()) as JobsResponse;
      setJobs(payload.jobs);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load jobs.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createJob = useCallback(async (input: NewJobInput) => {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const payload = (await response.json()) as Partial<JobResponse> & { errors?: unknown };
    if (!response.ok || !payload.job) {
      throw payload;
    }
    setJobs((current) => [...current, payload.job as JobSeed]);
    return payload.job as JobSeed;
  }, []);

  const editJob = useCallback(async (jobId: string, input: NewJobInput) => {
    const response = await fetch(`/api/jobs/${jobId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "edit", ...input }),
    });
    const payload = (await response.json()) as Partial<JobResponse> & { errors?: unknown };
    if (!response.ok || !payload.job) {
      throw payload;
    }
    setJobs((current) => replaceJob(current, payload.job as JobSeed));
    return payload.job as JobSeed;
  }, []);

  const updateJob = useCallback(async (jobId: string, action: "pause" | "resume" | "finish") => {
    const response = await fetch(`/api/jobs/${jobId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!response.ok) throw new Error(`Job update failed with ${response.status}`);
    const payload = (await response.json()) as JobResponse;
    setJobs((current) => replaceJob(current, payload.job));
    return payload.job;
  }, []);

  return {
    jobs,
    error,
    refresh,
    createJob,
    editJob,
    pauseJob: (jobId: string) => updateJob(jobId, "pause"),
    resumeJob: (jobId: string) => updateJob(jobId, "resume"),
    finishJob: (jobId: string) => updateJob(jobId, "finish"),
  };
}
