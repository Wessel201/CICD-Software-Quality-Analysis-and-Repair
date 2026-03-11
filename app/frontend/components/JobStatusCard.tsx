import type { JobStatus } from "../types";

const STATUS_LABEL: Record<JobStatus, string> = {
  pending: "Queued…",
  running: "Analyzing…",
  ready_for_repair: "Analysis Complete",
  completed: "Complete",
  failed: "Failed",
};

const STATUS_COLOR: Record<JobStatus, string> = {
  pending: "text-amber-500",
  running: "text-indigo-500",
  ready_for_repair: "text-green-500",
  completed: "text-green-500",
  failed: "text-red-500",
};

interface JobStatusCardProps {
  jobId: string;
  status: JobStatus;
}

export function JobStatusCard({ jobId, status }: JobStatusCardProps) {
  return (
    <div className="flex flex-col items-center gap-5 py-4">
      <svg
        className="w-12 h-12 text-indigo-500 animate-spin"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
        />
      </svg>
      <div className="text-center">
        <p className={`text-lg font-semibold ${STATUS_COLOR[status]}`}>
          {STATUS_LABEL[status]}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Job ID: <code className="font-mono">{jobId}</code>
        </p>
      </div>
    </div>
  );
}
