import type { FileDiff } from "../components/DiffViewer";

export type JobStatus = "pending" | "running" | "completed" | "failed";

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
  artifacts?: { artifact_id: string; name: string }[];
  diffs?: FileDiff[];
}
