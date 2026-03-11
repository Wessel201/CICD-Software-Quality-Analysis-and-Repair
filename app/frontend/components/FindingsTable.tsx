"use client";

import { useState, useMemo } from "react";
import type { Finding } from "../types";

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const SEVERITY_COLOURS: Record<string, string> = {
  critical: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300",
  high: "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300",
  medium:
    "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300",
  low: "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300",
};

type SortCol = "severity" | "file" | "tool" | "rule" | "category";
type SortDir = "asc" | "desc";

const ALL = "all";
const PAGE_SIZE = 10;

/** Returns only the final path segment, e.g. "/code/uploads/.../utils.py" → "utils.py" */
function basename(path: string): string {
  return path.split("/").pop() ?? path;
}

interface Props {
  findings: Finding[];
  selectedFinding: Finding | null;
  onSelect: (f: Finding) => void;
}

export function FindingsTable({ findings, selectedFinding, onSelect }: Props) {
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>(ALL);
  const [toolFilter, setToolFilter] = useState<string>(ALL);
  const [fileFilter, setFileFilter] = useState<string>(ALL);
  const [ruleFilter, setRuleFilter] = useState<string>(ALL);
  const [categoryFilter, setCategoryFilter] = useState<string>(ALL);
  const [sortCol, setSortCol] = useState<SortCol>("severity");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  // Unique values for filter dropdowns
  const uniqueFiles = useMemo(
    () => Array.from(new Set(findings.map((f) => basename(f.file)))).sort(),
    [findings],
  );
  const uniqueTools = useMemo(
    () => Array.from(new Set(findings.map((f) => f.tool))).sort(),
    [findings],
  );
  const uniqueRules = useMemo(
    () => Array.from(new Set(findings.map((f) => f.rule_id))).sort(),
    [findings],
  );
  const uniqueCategories = useMemo(
    () => Array.from(new Set(findings.map((f) => f.category))).sort(),
    [findings],
  );

  // Severity breakdown counts (unfiltered)
  const severityCounts = useMemo(
    () =>
      findings.reduce<Record<string, number>>(
        (acc, f) => ({ ...acc, [f.severity]: (acc[f.severity] ?? 0) + 1 }),
        {},
      ),
    [findings],
  );

  const filtered = useMemo(() => {
    let result = findings;
    if (severityFilter !== ALL)
      result = result.filter((f) => f.severity === severityFilter);
    if (toolFilter !== ALL)
      result = result.filter((f) => f.tool === toolFilter);
    if (fileFilter !== ALL)
      result = result.filter((f) => basename(f.file) === fileFilter);
    if (ruleFilter !== ALL)
      result = result.filter((f) => f.rule_id === ruleFilter);
    if (categoryFilter !== ALL)
      result = result.filter((f) => f.category === categoryFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((f) => f.message.toLowerCase().includes(q));
    }
    return result;
  }, [
    findings,
    severityFilter,
    toolFilter,
    fileFilter,
    ruleFilter,
    categoryFilter,
    search,
  ]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortCol === "severity") {
        cmp =
          (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
      } else if (sortCol === "file") {
        cmp =
          basename(a.file).localeCompare(basename(b.file)) || a.line - b.line;
      } else if (sortCol === "tool") {
        cmp = a.tool.localeCompare(b.tool);
      } else if (sortCol === "rule") {
        cmp = a.rule_id.localeCompare(b.rule_id);
      } else if (sortCol === "category") {
        cmp = a.category.localeCompare(b.category);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePageIndex = Math.min(page, totalPages - 1);
  const pageItems = sorted.slice(
    safePageIndex * PAGE_SIZE,
    safePageIndex * PAGE_SIZE + PAGE_SIZE,
  );

  function toggleSort(col: SortCol) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(0);
  }

  function SortIcon({ col }: { col: SortCol }) {
    const isActive = sortCol === col;
    if (!isActive) {
      return (
        <svg
          className="w-3 h-3 text-gray-400 dark:text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 10l5-5 5 5"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 14l5 5 5-5"
          />
        </svg>
      );
    }
    return (
      <svg
        className="w-3 h-3 text-indigo-500"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d={sortDir === "asc" ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"}
        />
      </svg>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Severity pill summary */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
        <span className="font-semibold text-gray-700 dark:text-gray-200">
          {findings.length} findings
        </span>
        {(["critical", "high", "medium", "low"] as const).map((sev) =>
          severityCounts[sev] ? (
            <span
              key={sev}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-semibold capitalize ${SEVERITY_COLOURS[sev]}`}
            >
              {severityCounts[sev]} {sev}
            </span>
          ) : null,
        )}
      </div>

      {/* Filters row — order matches column headers: Severity | Tool | File | Rule | Message */}
      <div className="flex flex-wrap gap-2 text-xs">
        {/* Severity */}
        <select
          value={severityFilter}
          onChange={(e) => {
            setSeverityFilter(e.target.value);
            setPage(0);
          }}
          className="px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        >
          <option value={ALL}>All severities</option>
          {(["critical", "high", "medium", "low"] as const).map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
        {/* Tool */}
        <select
          value={toolFilter}
          onChange={(e) => {
            setToolFilter(e.target.value);
            setPage(0);
          }}
          className="px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        >
          <option value={ALL}>All tools</option>
          {uniqueTools.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {/* File */}
        <select
          value={fileFilter}
          onChange={(e) => {
            setFileFilter(e.target.value);
            setPage(0);
          }}
          className="px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        >
          <option value={ALL}>All files</option>
          {uniqueFiles.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        {/* Rule */}
        <select
          value={ruleFilter}
          onChange={(e) => {
            setRuleFilter(e.target.value);
            setPage(0);
          }}
          className="px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        >
          <option value={ALL}>All rules</option>
          {uniqueRules.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        {/* Message search */}
        <input
          type="text"
          placeholder="Search message…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="flex-1 min-w-36 px-2.5 py-1.5 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
      </div>

      {/* Table */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-xs table-fixed">
          <colgroup>
            <col className="w-[80px]" />
            <col className="w-[60px]" />
            <col className="w-[110px]" />
            <col className="w-[72px]" />
            <col className="w-[80px]" />
            <col />
          </colgroup>
          <thead className="bg-gray-50 dark:bg-gray-700/60 text-gray-500 dark:text-gray-400 uppercase tracking-wide select-none">
            {/* Sort header row */}
            <tr>
              {(
                [
                  ["severity", "Severity"],
                  ["tool", "Tool"],
                  ["file", "File : Line"],
                  ["rule", "Rule"],
                  ["category", "Category"],
                ] as [SortCol, string][]
              ).map(([col, label]) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  onClick={() => toggleSort(col)}
                >
                  <span className="inline-flex items-center gap-1">
                    {label}
                    <SortIcon col={col} />
                  </span>
                </th>
              ))}
              <th className="px-3 py-2 text-left">Message</th>
            </tr>
            {/* Filter row — cells align exactly with colgroup widths */}
            <tr className="border-t border-gray-200 dark:border-gray-600">
              {(
                [
                  [
                    severityFilter,
                    setSeverityFilter,
                    (["critical", "high", "medium", "low"] as const).map(
                      (s) => ({
                        v: s,
                        l: s.charAt(0).toUpperCase() + s.slice(1),
                      }),
                    ),
                  ],
                  [
                    toolFilter,
                    setToolFilter,
                    uniqueTools.map((t) => ({ v: t, l: t })),
                  ],
                  [
                    fileFilter,
                    setFileFilter,
                    uniqueFiles.map((f) => ({ v: f, l: f })),
                  ],
                  [
                    ruleFilter,
                    setRuleFilter,
                    uniqueRules.map((r) => ({ v: r, l: r })),
                  ],
                  [
                    categoryFilter,
                    setCategoryFilter,
                    uniqueCategories.map((c) => ({ v: c, l: c })),
                  ],
                ] as [string, (v: string) => void, { v: string; l: string }[]][]
              ).map(([val, set, opts], i) => (
                <th key={i} className="px-2 pb-2 pt-1">
                  <select
                    value={val}
                    onChange={(e) => {
                      set(e.target.value);
                      setPage(0);
                    }}
                    className="w-full text-xs px-1.5 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 normal-case font-normal focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  >
                    <option value={ALL}>All</option>
                    {opts.map(({ v, l }) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </th>
              ))}
              <th className="px-2 pb-2 pt-1">
                <input
                  type="text"
                  placeholder="Search message…"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(0);
                  }}
                  className="w-full text-xs px-1.5 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 normal-case font-normal focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {pageItems.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-6 text-center text-gray-400 dark:text-gray-500"
                >
                  No findings match your filters.
                </td>
              </tr>
            )}
            {pageItems.map((f, i) => {
              const isSelected = selectedFinding === f;
              return (
                <tr
                  key={`${f.file}-${f.line}-${i}`}
                  onClick={() => onSelect(f)}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-indigo-50 dark:bg-indigo-900/25"
                      : "hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  }`}
                >
                  <td className="px-3 py-2.5">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full font-semibold capitalize ${SEVERITY_COLOURS[f.severity] ?? ""}`}
                    >
                      {f.severity}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-gray-600 dark:text-gray-400 truncate">
                    {f.tool}
                  </td>
                  <td
                    className="px-3 py-2.5 font-mono text-gray-600 dark:text-gray-400 truncate"
                    title={`${f.file}:${f.line}`}
                  >
                    {basename(f.file)}:{f.line}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-gray-500 dark:text-gray-400 truncate">
                    {f.rule_id}
                  </td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 truncate capitalize">
                    {f.category}
                  </td>
                  <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 truncate">
                    {f.message}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={safePageIndex === 0}
            className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>
          <span>
            {safePageIndex * PAGE_SIZE + 1}–
            {Math.min((safePageIndex + 1) * PAGE_SIZE, sorted.length)} of{" "}
            {sorted.length}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={safePageIndex === totalPages - 1}
            className="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
