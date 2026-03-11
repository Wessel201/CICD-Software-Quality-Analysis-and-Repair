"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { DiffViewer, diffStats } from "./DiffViewer";
import type { Finding, JobResult } from "../types";
import { downloadModifiedFile, downloadAllAsZip } from "../lib/download";
import { FindingDetailPanel } from "./FindingDetailPanel";
import { FindingsTable } from "./FindingsTable";
import { FileMapView } from "./FileMapView";

const PAGE_SIZE = 5;

type Tab = "summary" | "detail" | "filemap" | "changes";

interface ResultsCardProps {
  result: JobResult;
}

export function ResultsCard({ result }: ResultsCardProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  // Accordion: which file path is currently expanded in File View
  const [expandedFilePath, setExpandedFilePath] = useState<string | null>(null);

  const findings = result.findings_before ?? [];
  const afterFindings = result.findings_after ?? [];
  const diffs = result.diffs ?? [];
  const hasFindings = findings.length > 0;
  const hasDiffs = diffs.length > 0;

  // Unique files sorted by finding count desc
  const uniqueFiles = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of findings) counts.set(f.file, (counts.get(f.file) ?? 0) + 1);
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([path, count]) => ({
        path,
        count,
        display: path.split("/").pop() ?? path,
      }));
  }, [findings]);

  const isFixed = (f: Finding) =>
    !afterFindings.some(
      (a) =>
        a.tool === f.tool &&
        a.rule_id === f.rule_id &&
        a.file === f.file &&
        a.line === f.line,
    );

  function handleSelectFinding(f: Finding) {
    setSelectedFinding(f);
    setActiveTab("detail");
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
            Analysis Complete
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
            onClick={() => setActiveTab("detail")}
            className={tabClass("detail")}
          >
            Detail
            {selectedFinding && (
              <span className="ml-1.5 inline-block w-2 h-2 rounded-full bg-indigo-500" />
            )}
          </button>
        )}

        {hasFindings && (
          <button
            type="button"
            onClick={() => setActiveTab("filemap")}
            className={tabClass("filemap")}
          >
            File View
          </button>
        )}

        {hasDiffs && (
          <button
            type="button"
            onClick={() => setActiveTab("changes")}
            className={tabClass("changes")}
          >
            Changes
            <span className="ml-1.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-full px-1.5 py-0.5">
              {diffs.length}
            </span>
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
          ) : hasDiffs ? (
            <MockDiffSummary diffs={diffs} />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
              No findings to display.
            </p>
          )}
        </>
      )}

      {/* ── Detail tab ── */}
      {activeTab === "detail" && (
        <div className="flex flex-col gap-3">
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

      {/* ── Changes tab ── */}
      {activeTab === "changes" && hasDiffs && <DiffViewer diffs={diffs} />}

      {/* ── File map tab ── */}
      {activeTab === "filemap" && hasFindings && (
        <div className="flex flex-col gap-0 divide-y divide-gray-200 dark:divide-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          {uniqueFiles.map(({ path, count, display }) => {
            const fileFindings = findings.filter((f) => f.file === path);
            const isOpen = expandedFilePath === path;

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
              <div key={path}>
                {/* File header — always visible */}
                <button
                  type="button"
                  onClick={() => setExpandedFilePath(isOpen ? null : path)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700/60 transition-colors text-left"
                >
                  <div className="flex items-center gap-3 min-w-0">
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
                  </div>
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
                  </div>
                </button>

                {/* Expanded file map */}
                {isOpen && (
                  <div className="border-t border-gray-200 dark:border-gray-700">
                    <FileMapView
                      jobId={result.job_id}
                      filePath={path}
                      findings={fileFindings}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
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

// ── Mock fallback: diffs summary table ────────────────────────────────────────

function MockDiffSummary({
  diffs,
}: {
  diffs: NonNullable<JobResult["diffs"]>;
}) {
  const [page, setPage] = useState(0);

  const fileStats = diffs.map((d) => ({
    filename: d.filename,
    ...diffStats(d.original, d.modified),
  }));
  const totalAdded = fileStats.reduce((s, f) => s + f.added, 0);
  const totalRemoved = fileStats.reduce((s, f) => s + f.removed, 0);
  const totalPages = Math.max(1, Math.ceil(fileStats.length / PAGE_SIZE));
  const pageIndex = Math.min(page, totalPages - 1);
  const pageItems = fileStats.slice(
    pageIndex * PAGE_SIZE,
    pageIndex * PAGE_SIZE + PAGE_SIZE,
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          <span className="font-semibold text-gray-800 dark:text-white">
            {fileStats.length}
          </span>{" "}
          {fileStats.length === 1 ? "file" : "files"} changed{" · "}
          <span className="text-green-600 dark:text-green-400 font-semibold">
            +{totalAdded}
          </span>{" "}
          added{" · "}
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

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col className="w-8" />
            <col />
            <col className="w-16" />
            <col className="w-16" />
            <col className="w-14" />
            <col className="w-24" />
            <col className="w-10" />
          </colgroup>
          <thead className="bg-gray-50 dark:bg-gray-700/60 text-gray-500 dark:text-gray-400 uppercase text-xs tracking-wide">
            <tr>
              <th className="px-3 py-2 text-right">#</th>
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
              const net = f.added - f.removed;
              return (
                <tr
                  key={f.filename}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
                >
                  <td className="px-3 py-2 text-right text-gray-400 font-mono text-xs">
                    {pageIndex * PAGE_SIZE + i + 1}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-800 dark:text-gray-200 truncate">
                    {f.filename}
                  </td>
                  <td className="px-3 py-2 text-right text-xs font-semibold text-green-600 dark:text-green-400">
                    +{f.added}
                  </td>
                  <td className="px-3 py-2 text-right text-xs font-semibold text-red-500 dark:text-red-400">
                    -{f.removed}
                  </td>
                  <td
                    className={`px-3 py-2 text-right text-xs font-semibold ${net > 0 ? "text-green-600 dark:text-green-400" : net < 0 ? "text-red-500 dark:text-red-400" : "text-gray-400"}`}
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
                      className="inline-flex items-center text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors"
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

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
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
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={pageIndex === totalPages - 1}
            className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
