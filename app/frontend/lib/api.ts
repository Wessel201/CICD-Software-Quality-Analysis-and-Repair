import type { Job, JobListItem, JobResult, ApiJobStatus } from "../types";

// get api base from env var, or default to localhost for development
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

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
    case "READY_FOR_REPAIR":
      return "ready_for_repair";
    case "FETCHING":
    case "ANALYZING":
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
  form.append("auto_repair", "false");
  if (file) {
    const uploadUrlRes = await fetch(`${API_BASE}/api/v1/jobs/upload-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name }),
    });
    if (!uploadUrlRes.ok) {
      throw new Error(`Upload URL error ${uploadUrlRes.status}`);
    }
    const uploadData = await uploadUrlRes.json();

    const s3Upload = await fetch(uploadData.upload_url, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    });
    if (!s3Upload.ok) {
      throw new Error(`S3 upload failed ${s3Upload.status}`);
    }

    form.append("s3_key", uploadData.s3_key);
    console.log("[API] POST /api/v1/jobs", {
      type: "direct_s3_upload",
      fileName: file.name,
      size: file.size,
      s3_key: uploadData.s3_key,
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
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Server error ${res.status}`);
  }
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
  phase: "before" | "after" = "before",
): Promise<{ lines: string[]; total: number }> {
  const url = `${API_BASE}/api/v1/jobs/${jobId}/source?file=${encodeURIComponent(filePath)}&phase=${phase}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function listJobs(): Promise<JobListItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/jobs`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.jobs ?? [];
  } catch {
    return [];
  }
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
}

export async function triggerRepair(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repair_strategy: "balanced" }),
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
}

export function sourceArchiveUrl(
  jobId: string,
  phase: "before" | "after" = "before",
): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/source/archive?phase=${phase}`;
}

export interface ArtifactInfo {
  artifact_id: number;
  artifact_type: string;
  storage_key: string;
  content_type: string | null;
}

export async function getJobArtifacts(jobId: string): Promise<ArtifactInfo[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/artifacts`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.artifacts ?? [];
  } catch {
    return [];
  }
}

export function artifactDownloadUrl(jobId: string, artifactId: number): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/artifacts/${artifactId}/download`;
}
