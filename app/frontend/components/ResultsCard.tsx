"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DiffViewer, diffStats } from "./DiffViewer";
import type { JobResult } from "../types";
import { downloadModifiedFile, downloadAllAsZip } from "../lib/download";

const PAGE_SIZE = 5;

interface ResultsCardProps {
  result: JobResult;
}

export function ResultsCard({ result }: ResultsCardProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"summary" | "changes">("summary");
  const [summaryPage, setSummaryPage] = useState(0);

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
            Analysis Complete
          </p>
          <p className="text-xs text-gray-400 font-mono">Job {result.job_id}</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={() => setActiveTab("summary")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "summary"
              ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          }`}
        >
          Summary
        </button>
        {result.diffs && result.diffs.length > 0 && (
          <button
            type="button"
            onClick={() => setActiveTab("changes")}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "changes"
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            Changes
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-full px-1.5 py-0.5 font-sans">
              {result.diffs.length}
            </span>
          </button>
        )}
      </div>

      {/* Summary tab — confusion matrix */}
      {activeTab === "summary" &&
        (() => {
          const diffs = result.diffs ?? [];
          const fileStats = diffs.map((d) => ({
            filename: d.filename,
            ...diffStats(d.original, d.modified),
          }));
          const totalAdded = fileStats.reduce((s, f) => s + f.added, 0);
          const totalRemoved = fileStats.reduce((s, f) => s + f.removed, 0);
          const totalPages = Math.max(
            1,
            Math.ceil(fileStats.length / PAGE_SIZE),
          );
          const pageIndex = Math.min(summaryPage, totalPages - 1);
          const pageItems = fileStats.slice(
            pageIndex * PAGE_SIZE,
            pageIndex * PAGE_SIZE + PAGE_SIZE,
          );

          return (
            <div className="flex flex-col gap-4">
              {/* Totals header */}
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  <span className="font-semibold text-gray-800 dark:text-white">
                    {fileStats.length}
                  </span>{" "}
                  {fileStats.length === 1 ? "file" : "files"} changed
                  {" · "}
                  <span className="text-green-600 dark:text-green-400 font-semibold">
                    +{totalAdded}
                  </span>{" "}
                  added
                  {" · "}
                  <span className="text-red-500 dark:text-red-400 font-semibold">
                    -{totalRemoved}
                  </span>{" "}
                  removed
                </p>
                {diffs.length > 0 && (
                  <button
                    type="button"
                    onClick={() => downloadAllAsZip(diffs)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors shrink-0"
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
                    Download All (.zip)
                  </button>
                )}
              </div>

              {/* Table */}
              {fileStats.length > 0 ? (
                <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700/60 text-gray-500 dark:text-gray-400 uppercase text-xs tracking-wide">
                      <tr>
                        <th className="px-3 py-2 text-right w-8">#</th>
                        <th className="px-3 py-2 text-left">File</th>
                        <th className="px-3 py-2 text-right">+Added</th>
                        <th className="px-3 py-2 text-right">−Removed</th>
                        <th className="px-3 py-2 text-right">Net</th>
                        <th className="px-3 py-2 text-center">Status</th>
                        <th className="px-3 py-2 text-center"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {pageItems.map((f, i) => {
                        const globalIdx = pageIndex * PAGE_SIZE + i + 1;
                        const net = f.added - f.removed;
                        return (
                          <tr
                            key={f.filename}
                            className="hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
                          >
                            <td className="px-3 py-2 text-right text-gray-400 font-mono">
                              {globalIdx}
                            </td>
                            <td className="px-3 py-2 font-mono text-gray-800 dark:text-gray-200">
                              {f.filename}
                            </td>
                            <td className="px-3 py-2 text-right font-semibold text-green-600 dark:text-green-400">
                              +{f.added}
                            </td>
                            <td className="px-3 py-2 text-right font-semibold text-red-500 dark:text-red-400">
                              -{f.removed}
                            </td>
                            <td
                              className={`px-3 py-2 text-right font-semibold ${
                                net > 0
                                  ? "text-green-600 dark:text-green-400"
                                  : net < 0
                                    ? "text-red-500 dark:text-red-400"
                                    : "text-gray-400"
                              }`}
                            >
                              {net > 0 ? `+${net}` : net}
                            </td>
                            <td className="px-3 py-2 text-center">
                              {f.added > 0 || f.removed > 0 ? (
                                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300">
                                  Modified
                                </span>
                              ) : (
                                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500">
                                  Unchanged
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <button
                                type="button"
                                title={`Download ${f.filename}`}
                                onClick={() => {
                                  const diff = diffs.find(
                                    (d) => d.filename === f.filename,
                                  );
                                  if (diff) downloadModifiedFile(diff);
                                }}
                                className="inline-flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors"
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
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
                  No file changes to display.
                </p>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <button
                    type="button"
                    onClick={() => setSummaryPage((p) => Math.max(0, p - 1))}
                    disabled={pageIndex === 0}
                    className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    ← Prev
                  </button>
                  <span>
                    Page {pageIndex + 1} of {totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setSummaryPage((p) => Math.min(totalPages - 1, p + 1))
                    }
                    disabled={pageIndex === totalPages - 1}
                    className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>
          );
        })()}

      {/* Changes tab */}
      {activeTab === "changes" && result.diffs && (
        <DiffViewer diffs={result.diffs} />
      )}

      <button
        onClick={() => router.push("/")}
        className="w-full py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm"
      >
        Analyze Another Project
      </button>
    </div>
  );
}
