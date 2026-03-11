"use client";

import type { Finding } from "../types";

const SEVERITY_COLOURS: Record<string, string> = {
  critical: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300",
  high: "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300",
  medium:
    "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300",
  low: "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300",
};

interface Props {
  finding: Finding;
  isFixed: boolean;
  onClose: () => void;
}

export function FindingDetailPanel({ finding, isFixed, onClose }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-xs">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-700/60 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`shrink-0 inline-block px-2 py-0.5 rounded-full font-semibold capitalize ${SEVERITY_COLOURS[finding.severity] ?? ""}`}
          >
            {finding.severity}
          </span>
          <span className="font-mono text-gray-500 dark:text-gray-400 truncate">
            {finding.tool} · {finding.rule_id}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span
            className={`inline-block px-2 py-0.5 rounded-full font-semibold ${
              isFixed
                ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300"
                : "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
            }`}
          >
            {isFixed ? "✓ Fixed" : "Still present"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            aria-label="Close"
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* File location breadcrumb */}
      <div className="px-3 py-1.5 bg-gray-50 dark:bg-gray-800/40 border-b border-gray-200 dark:border-gray-700 font-mono text-gray-400 dark:text-gray-500">
        <span
          title={`${finding.file}:${finding.line}`}
          className="block truncate"
        >
          {finding.file} &nbsp;·&nbsp; line {finding.line}
        </span>
      </div>

      {/* Before: the issue */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <div className="px-3 py-1 bg-red-50 dark:bg-red-950/60 border-b border-red-100 dark:border-red-900/40 font-sans font-semibold text-red-600 dark:text-red-400">
          − issue found (line {finding.line})
        </div>
        <pre className="px-4 py-3 bg-red-50/50 dark:bg-red-950/20 font-mono text-red-800 dark:text-red-300 whitespace-pre-wrap break-words leading-relaxed">
          {finding.message}
        </pre>
      </div>

      {/* After: the suggestion */}
      <div>
        <div className="px-3 py-1 bg-green-50 dark:bg-green-950/60 border-b border-green-100 dark:border-green-900/40 font-sans font-semibold text-green-600 dark:text-green-400">
          + suggested fix
        </div>
        <pre className="px-4 py-3 bg-green-50/50 dark:bg-green-950/20 font-mono text-green-800 dark:text-green-300 whitespace-pre-wrap break-words leading-relaxed">
          {finding.suggestion || "No suggestion available for this rule."}
        </pre>
      </div>
    </div>
  );
}
