import type { FileDiff } from "../components/DiffViewer";

// Statuses used internally by the frontend (normalised)
export type JobStatus =
  | "pending"
  | "running"
  | "ready_for_repair"
  | "completed"
  | "failed";

// All status strings the real API can return
export type ApiJobStatus =
  | "QUEUED"
  | "FETCHING"
  | "ANALYZING"
  | "READY_FOR_REPAIR"
  | "REPAIRING"
  | "REANALYZING"
  | "DONE"
  | "FAILED";

export interface Finding {
  tool: string;
  rule_id: string;
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  file: string;
  line: number;
  message: string;
  suggestion: string;
  /** Source code lines around the finding, populated by the backend */
  snippet?: string[];
  /** 1-based line number of snippet[0] */
  snippet_start?: number;
}

export interface PatchInfo {
  file: string;
  diff_url: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  source_type?: string;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  summary?: string;
  issues_found?: number;
  findings_before?: Finding[];
  findings_after?: Finding[];
  patches?: PatchInfo[];
  artifacts?: { artifact_id: string; name: string }[];
  diffs?: FileDiff[];
}

export interface JobListItem {
  job_id: string;
  /** Raw API status, e.g. "DONE", "FAILED" */
  status: string;
  created_at: string;
  finished_at: string | null;
  source_label: string | null;
}
