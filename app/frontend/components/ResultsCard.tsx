"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Finding, JobResult, JobStatus } from "../types";
import {
  artifactDownloadUrl,
  deleteJob,
  getJobArtifacts,
  getJobSourceFile,
  sourceArchiveUrl,
} from "../lib/api";
import { FindingDetailPanel } from "./FindingDetailPanel";
import { FindingsTable } from "./FindingsTable";
import { FileMapView } from "./FileMapView";

function normPath(p: string) {
  return p.replace(/\\/g, "/").replace(/^\.\//, "");
}

type Tab = "summary" | "detail" | "filemap";

interface ResultsCardProps {
  result: JobResult;
  jobStatus: JobStatus;
  onRepair: () => Promise<void>;
}

export function ResultsCard({ result, jobStatus, onRepair }: ResultsCardProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  // Accordion: which file path is currently expanded in File View
  const [expandedFilePath, setExpandedFilePath] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailNotice, setDetailNotice] = useState<string | null>(null);
  const [llmFileState, setLlmFileState] = useState<
    Record<string, "idle" | "sending" | "done">
  >({});
  const [llmArchiveState, setLlmArchiveState] = useState<
    "idle" | "sending" | "done"
  >("idle");
  const [repairedArchiveUrl, setRepairedArchiveUrl] = useState<string | null>(
    null,
  );
  const [downloadNotice, setDownloadNotice] = useState<string | null>(null);

  const findings = result.findings_before ?? [];
  const afterFindings = result.findings_after ?? [];
  const hasFindings = findings.length > 0;
  const hasRepaired = afterFindings.length > 0;
  const anyFileLlmDone = Object.values(llmFileState).some((s) => s === "done");

  useEffect(() => {
    let cancelled = false;
    getJobArtifacts(result.job_id)
      .then((artifacts) => {
        if (cancelled) return;
        const repaired = artifacts.find(
          (artifact) => artifact.artifact_type === "repaired_source_archive",
        );
        if (!repaired || repaired.artifact_id == null) {
          setRepairedArchiveUrl(null);
          return;
        }
        setRepairedArchiveUrl(
          artifactDownloadUrl(result.job_id, repaired.artifact_id),
        );
      })
      .catch(() => {
        if (!cancelled) {
          setRepairedArchiveUrl(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [result.job_id, jobStatus]);

  // Unique files sorted by finding count desc.
  // Two findings with different full paths but the same basename are merged
  // (handles cases where the analyser scans both original/ and modified/ trees).
  const uniqueFiles = useMemo(() => {
    const groups = new Map<string, { originalPath: string; count: number }>();
    for (const f of findings) {
      // Key by the final filename component so e.g. original/utils.py and
      // modified/utils.py merge into a single entry.
      const key = normPath(f.file).split("/").pop()!.toLowerCase();
      const g = groups.get(key);
      if (g) g.count++;
      else groups.set(key, { originalPath: f.file, count: 1 });
    }
    return Array.from(groups.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .map(([basename, { originalPath, count }]) => ({
        basename,
        originalPath,
        count,
        display:
          originalPath.split("/").pop()?.split("\\").pop() ?? originalPath,
      }));
  }, [findings]);

  async function handleDownloadFile(
    filePath: string,
    phase: "before" | "after",
  ) {
    const filename = filePath.split("/").pop() ?? filePath;
    try {
      const data = await getJobSourceFile(result.job_id, filePath, phase);
      const blob = new Blob([data.lines.join("\n")], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (phase === "after" ? "modified_" : "") + filename;
      a.click();
      URL.revokeObjectURL(a.href);
      setDownloadNotice(null);
    } catch {
      if (phase === "after") {
        setDownloadNotice(
          "Modified download is not ready yet. Please wait for repair to complete and try again.",
        );
      } else {
        setDownloadNotice("Could not download source file right now. Please try again.");
      }
    }
  }

  async function handleSendAllToLlm() {
    setLlmArchiveState("sending");
    console.log(`[LLM] Sending all files to LLM for job: ${result.job_id}`);
    try {
      await onRepair();
    } catch {
      setLlmArchiveState("idle");
      return;
    }
    console.log(`[LLM] All files received by LLM for job: ${result.job_id}`);
    const allDone: Record<string, "done"> = {};
    for (const { basename } of uniqueFiles) allDone[basename] = "done";
    setLlmFileState((prev) => ({ ...prev, ...allDone }));
    setLlmArchiveState("done");
  }

  async function handleSendToLlm(basename: string, filePath: string) {
    setLlmFileState((prev) => ({ ...prev, [basename]: "sending" }));
    console.log(`[LLM] Sending file to LLM: ${filePath}`);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    console.log(`[LLM] File received by LLM: ${filePath}`);
    setLlmFileState((prev) => ({ ...prev, [basename]: "done" }));
  }

  const isFixed = (f: Finding) =>
    !afterFindings.some(
      (a) =>
        a.tool === f.tool &&
        a.rule_id === f.rule_id &&
        a.file === f.file &&
        a.line === f.line,
    );

  async function handleSelectFinding(f: Finding) {
    setSelectedFinding(f);
    setActiveTab("detail");
    setDetailNotice(null);

    if (f.snippet && f.snippet.length > 0) {
      return;
    }

    setDetailLoading(true);
    try {
      const data = await getJobSourceFile(result.job_id, f.file, "before");
      const idx = Math.max(0, f.line - 1);
      const start = Math.max(0, idx - 3);
      const end = Math.min(data.lines.length, idx + 4);
      const snippet = data.lines.slice(start, end);

      setSelectedFinding((prev) =>
        prev && prev.file === f.file && prev.line === f.line
          ? {
              ...prev,
              snippet,
              snippet_start: start + 1,
            }
          : prev,
      );
    } catch {
      setDetailNotice(
        "Source code context is not available yet. The issue details are shown without inline code.",
      );
    } finally {
      setDetailLoading(false);
    }
  }

  function tabClass(tab: Tab) {
    const active = "border-indigo-500 text-indigo-600 dark:text-indigo-400";
    const inactive =
      "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300";
    return `px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab ? active : inactive}`;
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
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
            {jobStatus === "completed"
              ? "Analysis & Repair Complete"
              : "Analysis Complete"}
          </p>
          <p className="text-xs text-gray-400 font-mono">Job {result.job_id}</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 gap-0">
        <button
          type="button"
          onClick={() => setActiveTab("summary")}
          className={tabClass("summary")}
        >
          Summary
          {hasFindings && (
            <span className="ml-1.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-full px-1.5 py-0.5">
              {findings.length}
            </span>
          )}
        </button>

        {hasFindings && (
          <button
            type="button"
            onClick={() => setActiveTab("filemap")}
            className={tabClass("filemap")}
          >
            File View
          </button>
        )}

        {hasFindings && (
          <button
            type="button"
            onClick={() => setActiveTab("detail")}
            className={tabClass("detail")}
          >
            Detail
          </button>
        )}
      </div>

      {/* ── Summary tab ── */}
      {activeTab === "summary" && (
        <>
          {hasFindings ? (
            <FindingsTable
              findings={findings}
              selectedFinding={selectedFinding}
              onSelect={handleSelectFinding}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
              No issues found.
            </p>
          )}
        </>
      )}

      {/* ── Detail tab ── */}
      {activeTab === "detail" && (
        <div className="flex flex-col gap-3">
          {detailLoading && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Loading code context...
            </p>
          )}
          {detailNotice && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {detailNotice}
            </p>
          )}
          {selectedFinding ? (
            <FindingDetailPanel
              finding={selectedFinding}
              displayFile={
                selectedFinding.file.split("/").pop() ?? selectedFinding.file
              }
              isFixed={isFixed(selectedFinding)}
              onClose={() => setActiveTab("summary")}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
              Click a row in the Summary tab to inspect a finding.
            </p>
          )}
        </div>
      )}

      {/* ── File map tab ── */}
      {activeTab === "filemap" && hasFindings && (
        <div className="flex flex-col gap-3">
          {/* Toolbar: archive downloads + LLM */}
          <div className="flex items-center gap-2 flex-wrap">
            <a
              href={sourceArchiveUrl(result.job_id, "before")}
              download
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 text-xs font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <svg
                className="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 3v12"
                />
              </svg>
              Original (.zip)
            </a>
            {((jobStatus === "completed" && hasRepaired) ||
              anyFileLlmDone ||
              llmArchiveState === "done") &&
              repairedArchiveUrl && (
              <a
                href={repairedArchiveUrl}
                download
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-green-400 dark:border-green-700 text-green-700 dark:text-green-400 text-xs font-semibold hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
              >
                <svg
                  className="w-3 h-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 3v12"
                  />
                </svg>
                Modified (.zip)
              </a>
            )}
            {((jobStatus === "completed" && hasRepaired) ||
              anyFileLlmDone ||
              llmArchiveState === "done") &&
              !repairedArchiveUrl && (
                <button
                  type="button"
                  onClick={() =>
                    setDownloadNotice(
                      "Modified archive is still being prepared. Please check back in a moment.",
                    )
                  }
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-500 dark:text-gray-400 text-xs font-semibold"
                >
                  Modified (.zip) not ready
                </button>
              )}
            {/* Send All to LLM — always visible, persists after sending */}
            <button
              type="button"
              disabled={llmArchiveState === "sending"}
              onClick={handleSendAllToLlm}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 text-xs font-semibold hover:bg-indigo-50 dark:hover:bg-indigo-900/20 disabled:opacity-50 transition-colors"
            >
              {llmArchiveState === "sending" ? (
                <>
                  <svg
                    className="w-3.5 h-3.5 animate-spin"
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
                  Sending…
                </>
              ) : (
                <>
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  {llmArchiveState === "done"
                    ? "Resend All to LLM"
                    : "Send All to LLM"}
                </>
              )}
            </button>
          </div>

          {downloadNotice && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {downloadNotice}
            </p>
          )}

          {/* File accordion */}
          <div className="flex flex-col gap-0 divide-y divide-gray-200 dark:divide-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            {uniqueFiles.map(({ basename, originalPath, count, display }) => {
              const fileFindings = findings.filter(
                (f) =>
                  (normPath(f.file).split("/").pop() ?? "").toLowerCase() ===
                  basename,
              );
              const isOpen = expandedFilePath === basename;

              // Severity breakdown for this file
              const sevCounts = fileFindings.reduce<Record<string, number>>(
                (acc, f) => ({
                  ...acc,
                  [f.severity]: (acc[f.severity] ?? 0) + 1,
                }),
                {},
              );
              const SEV_COLOUR: Record<string, string> = {
                critical: "#ef4444",
                high: "#f97316",
                medium: "#eab308",
                low: "#3b82f6",
              };

              return (
                <div key={basename}>
                  {/* File header — always visible */}
                  <div className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 text-left">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedFilePath(isOpen ? null : basename)
                      }
                      className="flex items-center gap-3 min-w-0 flex-1 hover:opacity-80 transition-opacity"
                    >
                      <svg
                        className={`w-3.5 h-3.5 shrink-0 text-gray-400 transition-transform ${
                          isOpen ? "rotate-90" : ""
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2.5}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                      <span className="font-mono font-semibold text-sm text-gray-800 dark:text-gray-100 truncate">
                        {display}
                      </span>
                    </button>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      {(["critical", "high", "medium", "low"] as const)
                        .filter((s) => sevCounts[s])
                        .map((s) => (
                          <span
                            key={s}
                            className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                            style={{
                              background: `${SEV_COLOUR[s]}22`,
                              color: SEV_COLOUR[s],
                              border: `1px solid ${SEV_COLOUR[s]}44`,
                            }}
                          >
                            {sevCounts[s]} {s}
                          </span>
                        ))}
                      <span className="text-xs text-gray-400">{count}</span>
                      {/* Download original */}
                      <button
                        type="button"
                        title="Download original"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadFile(originalPath, "before");
                        }}
                        className="inline-flex items-center text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                      >
                        <svg
                          className="w-3.5 h-3.5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 3v12"
                          />
                        </svg>
                      </button>
                      {/* Download modified — shown only after this file sent to LLM (or backend repaired) */}
                      {((jobStatus === "completed" && hasRepaired) ||
                        llmFileState[basename] === "done") && (
                        <button
                          type="button"
                          title="Download modified"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadFile(originalPath, "after");
                          }}
                          className="inline-flex items-center text-green-500 hover:text-green-700 dark:hover:text-green-400 transition-colors"
                        >
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 3v12"
                            />
                          </svg>
                        </button>
                      )}
                      {/* Send to LLM — persists after sending */}
                      <button
                        type="button"
                        title="Send to LLM for repair"
                        disabled={llmFileState[basename] === "sending"}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSendToLlm(basename, originalPath);
                        }}
                        className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 disabled:opacity-50 transition-colors"
                      >
                        {llmFileState[basename] === "sending" ? (
                          <>
                            <svg
                              className="w-3 h-3 animate-spin"
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
                            Sending…
                          </>
                        ) : (
                          <>
                            <svg
                              className="w-3 h-3"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 10V3L4 14h7v7l9-11h-7z"
                              />
                            </svg>
                            {llmFileState[basename] === "done"
                              ? "Resend to LLM"
                              : "Send to LLM"}
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Expanded file map */}
                  {isOpen && (
                    <div className="border-t border-gray-200 dark:border-gray-700">
                      <FileMapView
                        jobId={result.job_id}
                        filePath={originalPath}
                        findings={fileFindings}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={() => router.push("/")}
          className="flex-1 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm"
        >
          Analyze Another Project
        </button>
        <button
          onClick={() => setShowDeleteModal(true)}
          className="flex-1 py-2.5 rounded-lg border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 font-semibold hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
        >
          Delete Job
        </button>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
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
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="flex-1 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={async () => {
                  setDeleting(true);
                  try {
                    await deleteJob(result.job_id);
                  } catch {
                    // Navigate home regardless
                  }
                  router.push("/");
                }}
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
