"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, deleteJob } from "../lib/api";
import type { JobListItem } from "../types";

const DEFAULT_VISIBLE = 3;

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RecentJobs() {
  const [jobs, setJobs] = useState<JobListItem[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);

  const doneJobs = jobs?.filter((j) => j.status === "DONE") ?? [];
  if (!jobs || doneJobs.length === 0) return null;

  const visible = showAll ? doneJobs : doneJobs.slice(0, DEFAULT_VISIBLE);
  const hiddenCount = doneJobs.length - DEFAULT_VISIBLE;

  const handleDelete = async (jobId: string) => {
    setDeleting(true);
    try {
      await deleteJob(jobId);
      setJobs((prev) => prev?.filter((j) => j.job_id !== jobId) ?? prev);
    } catch {
      // Silently ignore; job may already be gone
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  };

  return (
    <div className="mt-8">
      <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-3 tracking-wide uppercase">
        Recent Jobs
      </h3>
      <ul className="flex flex-col gap-2">
        {visible.map((job) => {
          const label = job.source_label ?? job.job_id;
          return (
            <li key={job.job_id} className="flex items-center gap-2">
              <Link
                href={`/results/${job.job_id}`}
                className="flex-1 flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700/60 transition-colors min-w-0"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="inline-block w-2 h-2 rounded-full shrink-0 bg-green-500" />
                  <div className="min-w-0">
                    <p className="font-medium text-sm text-gray-800 dark:text-gray-100 truncate">
                      {label}
                    </p>
                    <p className="font-mono text-[10px] text-gray-400 truncate">
                      {job.job_id}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-gray-400 shrink-0 ml-4">
                  {job.finished_at
                    ? formatDate(job.finished_at)
                    : formatDate(job.created_at)}
                </span>
              </Link>
              <button
                type="button"
                title="Delete job"
                onClick={() => setConfirmDeleteId(job.job_id)}
                className="shrink-0 p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </li>
          );
        })}
      </ul>
      {!showAll && hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mt-3 w-full text-sm text-gray-500 dark:text-gray-400 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors"
        >
          Show {hiddenCount} more
        </button>
      )}
      {showAll && doneJobs.length > DEFAULT_VISIBLE && (
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="mt-3 w-full text-sm text-gray-500 dark:text-gray-400 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors"
        >
          Show less
        </button>
      )}

      {/* Delete confirmation modal */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-2">
              Delete this job?
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">
              This will permanently remove the job and all its results. This
              action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setConfirmDeleteId(null)}
                disabled={deleting}
                className="flex-1 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => handleDelete(confirmDeleteId)}
                className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold transition-colors text-sm disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {deleting && (
                  <svg
                    className="w-4 h-4 animate-spin"
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
                )}
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
