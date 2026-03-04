"use client";

import { useState, useRef, useCallback } from "react";
import { useTheme } from "../providers/ThemeProvider";

const ACCEPTED_EXTENSIONS = [".zip", ".py"];
const API_BASE = "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

type JobStatus = "pending" | "running" | "completed" | "failed";

interface Job {
  job_id: string;
  status: JobStatus;
  source_type?: string;
}

interface JobResult {
  job_id: string;
  status: JobStatus;
  summary?: string;
  issues_found?: number;
  artifacts?: { artifact_id: string; name: string }[];
}

type PageState = "idle" | "submitting" | "polling" | "done" | "error";

// ── Helpers ────────────────────────────────────────────────────────────────────

function getFileWarning(name: string): string | null {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `"${name}" is not supported. Only .zip archives and .py files are accepted.`;
  }
  return null;
}

// Mock fallback used when the API is unreachable
function mockCreateJob(): Promise<Job> {
  return new Promise((resolve) =>
    setTimeout(
      () =>
        resolve({
          job_id: `mock-${Date.now()}`,
          status: "pending",
          source_type: "mock",
        }),
      600,
    ),
  );
}

function mockPollJob(job_id: string, attempt: number): Promise<Job> {
  const status: JobStatus = attempt < 3 ? "running" : "completed";
  return new Promise((resolve) =>
    setTimeout(() => resolve({ job_id, status }), 800),
  );
}

function mockGetResults(job_id: string): Promise<JobResult> {
  return new Promise((resolve) =>
    setTimeout(
      () =>
        resolve({
          job_id,
          status: "completed",
          summary: "Analysis complete (mock). 3 issues detected.",
          issues_found: 3,
          artifacts: [
            { artifact_id: "art-1", name: "report.json" },
            { artifact_id: "art-2", name: "diff.patch" },
          ],
        }),
      400,
    ),
  );
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function Home() {
  const { theme } = useTheme();

  // Form state
  const [fileObj, setFileObj] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [fileWarning, setFileWarning] = useState<string | null>(null);
  const [githubUrl, setGithubUrl] = useState<string>("");

  // Job state
  const [pageState, setPageState] = useState<PageState>("idle");
  const [jobId, setJobId] = useState<string>("");
  const [jobStatus, setJobStatus] = useState<JobStatus>("pending");
  const [result, setResult] = useState<JobResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [isMock, setIsMock] = useState(false);

  const pollCountRef = useRef(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── API calls ────────────────────────────────────────────────────────────────

  const createJob = useCallback(async (): Promise<Job> => {
    if (fileObj) {
      const form = new FormData();
      form.append("file", fileObj);
      console.log("[API] POST /api/v1/jobs", { type: "file", fileName: fileObj.name, size: fileObj.size });
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
  }, [fileObj, githubUrl]);

  const pollJob = useCallback(
    async (id: string, useMock: boolean, attempt: number) => {
      try {
        let job: Job;
        if (useMock) {
          console.log("[Mock] GET /api/v1/jobs/:id", { id, attempt });
          job = await mockPollJob(id, attempt);
          console.log("[Mock] GET /api/v1/jobs/:id → response", job);
        } else {
          console.log(`[API] GET /api/v1/jobs/${id}`, { attempt });
          const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`);
          if (!res.ok) throw new Error(`Server error ${res.status}`);
          job = await res.json();
          console.log(`[API] GET /api/v1/jobs/${id} → response`, job);
        }

        setJobStatus(job.status);

        if (job.status === "completed") {
          // Fetch results
          let results: JobResult;
          if (useMock) {
            console.log("[Mock] GET /api/v1/jobs/:id/results", { id });
            results = await mockGetResults(id);
            console.log("[Mock] GET /api/v1/jobs/:id/results → response", results);
          } else {
            console.log(`[API] GET /api/v1/jobs/${id}/results`);
            const rRes = await fetch(`${API_BASE}/api/v1/jobs/${id}/results`);
            results = rRes.ok
              ? await rRes.json()
              : { job_id: id, status: "completed" };
            console.log(`[API] GET /api/v1/jobs/${id}/results → response`, results);
          }
          setResult(results);
          setPageState("done");
        } else if (job.status === "failed") {
          setErrorMsg("The analysis job failed on the server.");
          setPageState("error");
        } else {
          // Still pending/running — keep polling
          pollCountRef.current += 1;
          pollTimerRef.current = setTimeout(
            () => pollJob(id, useMock, pollCountRef.current),
            2000,
          );
        }
      } catch {
        setErrorMsg("Lost connection while polling for job status.");
        setPageState("error");
      }
    },
    [],
  );

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileObj(file);
    setFileName(file.name);
    setFileWarning(getFileWarning(file.name));
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    setFileObj(file);
    setFileName(file.name);
    setFileWarning(getFileWarning(file.name));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (fileWarning) return;

    setPageState("submitting");
    setErrorMsg("");
    setResult(null);
    pollCountRef.current = 0;

    let job: Job;
    let useMock = false;

    try {
      job = await createJob();
    } catch (err) {
      // API unreachable — use mock
      console.warn("[API] POST /api/v1/jobs failed, falling back to mock mode", err);
      useMock = true;
      setIsMock(true);
      console.log("[Mock] POST /api/v1/jobs");
      job = await mockCreateJob();
      console.log("[Mock] POST /api/v1/jobs → response", job);
    }

    setJobId(job.job_id);
    setJobStatus(job.status);
    setPageState("polling");

    pollJob(job.job_id, useMock, 0);
  };

  const handleReset = () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setPageState("idle");
    setFileObj(null);
    setFileName("");
    setFileWarning(null);
    setGithubUrl("");
    setJobId("");
    setJobStatus("pending");
    setResult(null);
    setErrorMsg("");
    setIsMock(false);
    pollCountRef.current = 0;
  };

  const canSubmit = (!!fileName && !fileWarning) || !!githubUrl;

  // ── Status label helpers ─────────────────────────────────────────────────────

  const statusLabel: Record<JobStatus, string> = {
    pending: "Queued…",
    running: "Analyzing…",
    completed: "Complete",
    failed: "Failed",
  };

  const statusColor: Record<JobStatus, string> = {
    pending: "text-amber-500",
    running: "text-indigo-500",
    completed: "text-green-500",
    failed: "text-red-500",
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 py-12 px-4 transition-colors duration-300">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <img
              src={theme === "dark" ? "/favicon.svg" : "/favicon-dark.svg"}
              alt="logo"
              className="w-10 h-10"
            />
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
              Code Quality Analyzer
            </h1>
          </div>
          <p className="text-gray-600 dark:text-gray-300">
            Upload your project and get AI-powered improvements
          </p>
        </div>

        {/* ── POLLING / DONE / ERROR card ── */}
        {(pageState === "polling" ||
          pageState === "done" ||
          pageState === "error") && (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 flex flex-col gap-6 transition-colors">
            {/* Error state */}
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
                  onClick={handleReset}
                  className="px-5 py-2 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            )}

            {/* Polling state */}
            {pageState === "polling" && (
              <div className="flex flex-col items-center gap-5 py-4">
                {/* Spinner */}
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
                  <p
                    className={`text-lg font-semibold ${statusColor[jobStatus]}`}
                  >
                    {statusLabel[jobStatus]}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Job ID: <code className="font-mono">{jobId}</code>
                  </p>
                </div>
              </div>
            )}

            {/* Done state */}
            {pageState === "done" && result && (
              <div className="flex flex-col gap-5">
                <div className="flex items-center gap-3">
                  <svg
                    className="w-8 h-8 text-green-500 shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div>
                    <p className="font-semibold text-gray-800 dark:text-white">
                      Analysis Complete
                    </p>
                    <p className="text-xs text-gray-400 font-mono">
                      Job {result.job_id}
                    </p>
                  </div>
                </div>

                {result.summary && (
                  <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700/50 rounded-lg px-4 py-3">
                    {result.summary}
                  </p>
                )}

                {typeof result.issues_found === "number" && (
                  <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-semibold text-indigo-600 dark:text-indigo-400 text-2xl">
                      {result.issues_found}
                    </span>
                    issues detected
                  </div>
                )}

                {result.artifacts && result.artifacts.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                      Artifacts
                    </p>
                    <ul className="flex flex-col gap-2">
                      {result.artifacts.map((a) => (
                        <li
                          key={a.artifact_id}
                          className="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 rounded-lg px-4 py-2"
                        >
                          <span className="text-sm text-gray-700 dark:text-gray-300 font-mono">
                            {a.name}
                          </span>
                          {!isMock && (
                            <a
                              href={`${API_BASE}/api/v1/jobs/${result.job_id}/artifacts/${a.artifact_id}/download`}
                              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-medium"
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Download
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Mock notice */}
                {isMock && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
                    <svg
                      className="w-4 h-4 shrink-0 text-amber-500"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-xs text-amber-700 dark:text-amber-400">
                      API unreachable — running in <strong>mock mode</strong>.
                      Results are simulated.
                    </span>
                  </div>
                )}

                <button
                  onClick={handleReset}
                  className="w-full py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm"
                >
                  Analyze Another Project
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── SUBMIT FORM (idle + submitting) ── */}
        {(pageState === "idle" || pageState === "submitting") && (
          <form
            onSubmit={handleSubmit}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 flex flex-col gap-8 transition-colors"
          >
            {/* GitHub Section */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                GitHub Repository URL
              </label>
              <input
                type="url"
                placeholder="https://github.com/username/repo"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                disabled={pageState === "submitting"}
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-colors disabled:opacity-60"
              />
            </div>

            {/* Divider */}
            <div className="flex items-center gap-4">
              <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
              <span className="text-sm font-medium text-gray-400 dark:text-gray-500">
                or
              </span>
              <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
            </div>

            {/* File Upload Section */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Upload Project File
              </label>

              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => document.getElementById("file-input")?.click()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  fileWarning
                    ? "border-red-400 dark:border-red-500 bg-red-50 dark:bg-red-900/10"
                    : "border-indigo-300 dark:border-indigo-600 bg-indigo-50 dark:bg-gray-700 hover:border-indigo-500 dark:hover:border-indigo-400"
                }`}
              >
                <svg
                  className={`w-12 h-12 mx-auto mb-3 ${fileWarning ? "text-red-400" : "text-indigo-400 dark:text-indigo-300"}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p
                  className={`font-medium text-sm ${fileWarning ? "text-red-600 dark:text-red-400" : "text-gray-600 dark:text-gray-300"}`}
                >
                  {fileName ? fileName : "Click to select or drag and drop"}
                </p>
                {!fileName && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    .zip or .py
                  </p>
                )}
              </div>

              <input
                id="file-input"
                type="file"
                accept=".zip,.py"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            {/* File warning */}
            {fileWarning && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
                <svg
                  className="w-4 h-4 shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                    clipRule="evenodd"
                  />
                </svg>
                {fileWarning}
              </p>
            )}

            <div className="flex items-center gap-2 mt-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
              <svg
                className="w-4 h-4 shrink-0 text-amber-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-xs text-amber-700 dark:text-amber-400">
                Only <strong>.zip</strong> archives and <strong>.py</strong>{" "}
                files are currently supported
              </span>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={!canSubmit || pageState === "submitting"}
              className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 ${
                canSubmit && pageState !== "submitting"
                  ? "bg-indigo-600 dark:bg-indigo-500 text-white hover:bg-indigo-700 dark:hover:bg-indigo-600"
                  : "bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed"
              }`}
            >
              {pageState === "submitting" && (
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
              {pageState === "submitting" ? "Submitting…" : "Analyze Project"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
