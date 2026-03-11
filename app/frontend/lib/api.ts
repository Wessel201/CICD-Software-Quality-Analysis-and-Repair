import type { Job, JobResult } from "../types";
import { MOCK_DIFFS } from "../mock";

export const API_BASE = "http://localhost:8000";

// ── Real API ──────────────────────────────────────────────────────────────────

export async function createJob(
  file: File | null,
  githubUrl: string,
): Promise<Job> {
  if (file) {
    const form = new FormData();
    form.append("file", file);
    console.log("[API] POST /api/v1/jobs", {
      type: "file",
      fileName: file.name,
      size: file.size,
    });
    const res = await fetch(`${API_BASE}/api/v1/jobs`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const job: Job = await res.json();
    console.log("[API] POST /api/v1/jobs → response", job);
    return job;
  } else {
    const payload = { source_type: "github", github_url: githubUrl };
    console.log("[API] POST /api/v1/jobs", payload);
    const res = await fetch(`${API_BASE}/api/v1/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const job: Job = await res.json();
    console.log("[API] POST /api/v1/jobs → response", job);
    return job;
  }
}

export async function pollJobStatus(id: string, attempt: number): Promise<Job> {
  console.log(`[API] GET /api/v1/jobs/${id}`, { attempt });
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const job: Job = await res.json();
  console.log(`[API] GET /api/v1/jobs/${id} → response`, job);
  return job;
}

export async function getJobResults(id: string): Promise<JobResult> {
  console.log(`[API] GET /api/v1/jobs/${id}/results`);
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}/results`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const results: JobResult = await res.json();
  console.log(`[API] GET /api/v1/jobs/${id}/results → response`, results);
  return results;
}

// ── Mock fallback (used when API is unreachable) ───────────────────────────────

export function mockCreateJob(): Promise<Job> {
  return new Promise((resolve) =>
    setTimeout(() => {
      const job: Job = {
        job_id: `mock-${Date.now()}`,
        status: "pending",
        source_type: "mock",
      };
      console.log("[Mock] POST /api/v1/jobs → response", job);
      resolve(job);
    }, 600),
  );
}

export function mockPollJobStatus(
  job_id: string,
  attempt: number,
): Promise<Job> {
  const status = attempt < 3 ? ("running" as const) : ("completed" as const);
  return new Promise((resolve) =>
    setTimeout(() => {
      const job: Job = { job_id, status };
      console.log("[Mock] GET /api/v1/jobs/:id → response", job);
      resolve(job);
    }, 800),
  );
}

export function mockGetResults(job_id: string): Promise<JobResult> {
  return new Promise((resolve) =>
    setTimeout(() => {
      const results: JobResult = {
        job_id,
        status: "completed",
        summary: "Analysis complete (mock). 3 issues detected across 2 files.",
        issues_found: 3,
        diffs: MOCK_DIFFS,
      };
      console.log("[Mock] GET /api/v1/jobs/:id/results → response", results);
      resolve(results);
    }, 400),
  );
}
