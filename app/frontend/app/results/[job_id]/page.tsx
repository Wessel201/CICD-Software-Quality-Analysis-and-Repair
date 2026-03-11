"use client";

import { use, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { JobStatusCard } from "../../../components/JobStatusCard";
import { ResultsCard } from "../../../components/ResultsCard";
import {
  pollJobStatus,
  getJobResults,
  mockPollJobStatus,
  mockGetResults,
} from "../../../lib/api";
import { getDiffsForFiles } from "../../../mock";
import type { JobResult, JobStatus } from "../../../types";

type PageState = "polling" | "done" | "error";

interface Props {
  params: Promise<{ job_id: string }>;
}

export default function ResultsPage({ params }: Props) {
  const { job_id } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();
  const filesParam = searchParams.get("files") ?? "*";

  const [pageState, setPageState] = useState<PageState>("polling");
  const [jobStatus, setJobStatus] = useState<JobStatus>("pending");
  const [result, setResult] = useState<JobResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const attemptRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        let job;
        try {
          job = await pollJobStatus(job_id, attemptRef.current);
        } catch {
          job = await mockPollJobStatus(job_id, attemptRef.current);
        }

        if (cancelled) return;
        setJobStatus(job.status);

        if (job.status === "completed") {
          let results: JobResult;
          try {
            results = await getJobResults(job_id);
          } catch {
            results = await mockGetResults(job_id);
          }
          // Attach locally-computed diffs based on submitted files
          results = { ...results, diffs: getDiffsForFiles(filesParam) };
          if (!cancelled) {
            setResult(results);
            setPageState("done");
          }
        } else if (job.status === "failed") {
          if (!cancelled) {
            setErrorMsg("The analysis job failed on the server.");
            setPageState("error");
          }
        } else {
          attemptRef.current += 1;
          timerRef.current = setTimeout(poll, 2000);
        }
      } catch {
        if (!cancelled) {
          setErrorMsg("Lost connection while polling for job status.");
          setPageState("error");
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [job_id, filesParam]);

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-gradient-to-br from-slate-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-300">
      {/* Fixed header */}
      <div className="flex-shrink-0 text-center py-6 px-4">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Analysis Results
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mt-1 text-sm">
          {pageState === "polling"
            ? "Processing your project…"
            : pageState === "done"
              ? "Your analysis is ready."
              : "Something went wrong."}
        </p>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 pb-8">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 transition-colors">
            {pageState === "polling" && (
              <JobStatusCard jobId={job_id} status={jobStatus} />
            )}

            {pageState === "error" && (
              <div className="flex flex-col items-center gap-4 text-center">
                <svg
                  className="w-14 h-14 text-red-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                  />
                </svg>
                <p className="text-red-600 dark:text-red-400 font-medium">
                  {errorMsg}
                </p>
                <button
                  onClick={() => router.push("/")}
                  className="px-5 py-2 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            )}

            {pageState === "done" && result && <ResultsCard result={result} />}
          </div>
        </div>
      </div>
    </div>
  );
}
