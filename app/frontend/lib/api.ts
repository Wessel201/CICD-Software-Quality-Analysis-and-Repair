import type { Job, JobResult, ApiJobStatus } from "../types";
import { MOCK_DIFFS } from "../mock";

export const API_BASE = "http://localhost:8000";

// ── Status normalisation ──────────────────────────────────────────────────────
// Maps the API's multi-step uppercase statuses to the four frontend states.

function normalizeStatus(raw: string): Job["status"] {
  switch (raw as ApiJobStatus) {
    case "DONE":
      return "completed";
    case "FAILED":
      return "failed";
    case "QUEUED":
      return "pending";
    case "FETCHING":
    case "ANALYZING":
    case "READY_FOR_REPAIR":
    case "REPAIRING":
    case "REANALYZING":
      return "running";
    default:
      // Already a normalised value (mock path) — pass through
      return raw as Job["status"];
  }
}

// ── Real API ──────────────────────────────────────────────────────────────────

export async function createJob(
  file: File | null,
  githubUrl: string,
): Promise<Job> {
  const form = new FormData();
  if (file) {
    form.append("file", file);
    console.log("[API] POST /api/v1/jobs", {
      type: "file",
      fileName: file.name,
      size: file.size,
    });
  } else {
    form.append("github_url", githubUrl);
    console.log("[API] POST /api/v1/jobs", {
      type: "github",
      github_url: githubUrl,
    });
  }
  const res = await fetch(`${API_BASE}/api/v1/jobs`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const raw = await res.json();
  const job: Job = { ...raw, status: normalizeStatus(raw.status) };
  console.log("[API] POST /api/v1/jobs → response", job);
  return job;
}

export async function pollJobStatus(id: string, attempt: number): Promise<Job> {
  console.log(`[API] GET /api/v1/jobs/${id}`, { attempt });
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const raw = await res.json();
  const job: Job = { ...raw, status: normalizeStatus(raw.status) };
  console.log(`[API] GET /api/v1/jobs/${id} → response`, job);
  return job;
}

export async function getJobResults(id: string): Promise<JobResult> {
  console.log(`[API] GET /api/v1/jobs/${id}/results`);
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}/results`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const raw = await res.json();
  console.log(`[API] GET /api/v1/jobs/${id}/results → response`, raw);

  // Map the real API shape to the frontend JobResult shape:
  // raw.summary = { before_total, after_total, reduction_pct }
  // raw.before / raw.after = Finding[]
  const summaryText = raw.summary
    ? `${raw.summary.before_total} issues found, reduced to ${raw.summary.after_total} (${raw.summary.reduction_pct.toFixed(1)}% reduction)`
    : undefined;

  const results: JobResult = {
    job_id: raw.job_id,
    status: normalizeStatus(raw.status ?? "DONE"),
    summary: summaryText,
    issues_found: raw.summary?.before_total,
    findings_before: raw.before,
    findings_after: raw.after,
    patches: raw.patches,
  };
  return results;
}

export async function getJobSourceFile(
  jobId: string,
  filePath: string,
): Promise<{ lines: string[]; total: number }> {
  const url = `${API_BASE}/api/v1/jobs/${jobId}/source?file=${encodeURIComponent(filePath)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
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
