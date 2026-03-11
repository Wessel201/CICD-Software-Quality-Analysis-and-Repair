"use client";

import type { Finding } from "../types";
import {
  UnifiedDiffView,
  type DiffHunk,
  type DiffLine,
} from "./UnifiedDiffView";

const SEVERITY_COLOURS: Record<string, string> = {
  critical: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300",
  high: "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300",
  medium:
    "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300",
  low: "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300",
};

function findingToHunk(f: Finding): DiffHunk {
  // If the backend returned a real code snippet, build a proper diff with context
  if (f.snippet && f.snippet.length > 0) {
    const start = f.snippet_start ?? 1;
    const findingIdx = f.line - start; // 0-based index of the finding line within snippet

    const lines: DiffLine[] = f.snippet.map((content, i) => {
      const lineNo = start + i;
      const isFindingLine = i === findingIdx;
      return {
        type: isFindingLine ? "del" : "context",
        oldNo: lineNo,
        newNo: isFindingLine ? null : lineNo,
        content,
      };
    });

    // Append the suggestion as "add" lines after the del line
    const addLines = (f.suggestion || "No suggestion available.")
      .split("\n")
      .filter((l) => l.trim());
    addLines.forEach((content, i) => {
      lines.splice(findingIdx + 1 + i, 0, {
        type: "add",
        oldNo: null,
        newNo: f.line + i,
        content,
      });
    });

    return {
      header: `@@ -${start},${f.snippet.length} +${start},${f.snippet.length - 1 + addLines.length} @@ ${f.rule_id}`,
      lines,
    };
  }

  // Fallback: display message/suggestion as prose diff (no source available)
  const delLines = f.message.split("\n").filter((l) => l.trim());
  const addLines = (f.suggestion || "No suggestion available for this rule.")
    .split("\n")
    .filter((l) => l.trim());
  return {
    header: `@@ -${f.line},${delLines.length} +${f.line},${addLines.length} @@ ${f.rule_id}`,
    lines: [
      ...delLines.map((content, i) => ({
        type: "del" as const,
        oldNo: f.line + i,
        newNo: null,
        content,
      })),
      ...addLines.map((content, i) => ({
        type: "add" as const,
        oldNo: null,
        newNo: f.line + i,
        content,
      })),
    ],
  };
}

interface Props {
  finding: Finding;
  /** Short display name, e.g. "utils.py" — pass from parent to avoid recomputing */
  displayFile: string;
  isFixed: boolean;
  onClose: () => void;
}

export function FindingDetailPanel({
  finding,
  displayFile,
  isFixed,
  onClose,
}: Props) {
  const hunk = findingToHunk(finding);

  return (
    <div className="flex flex-col gap-2 text-xs">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-700/60 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 min-w-0 overflow-hidden">
          <span
            className={`shrink-0 inline-block px-2 py-0.5 rounded-full font-semibold capitalize ${SEVERITY_COLOURS[finding.severity] ?? ""}`}
          >
            {finding.severity}
          </span>
          <span className="font-mono text-gray-500 dark:text-gray-400 truncate">
            {finding.tool}
          </span>
          <span className="text-gray-300 dark:text-gray-600 shrink-0">·</span>
          <span className="font-mono text-gray-500 dark:text-gray-400 truncate">
            {finding.rule_id}
          </span>
          <span className="text-gray-300 dark:text-gray-600 shrink-0">·</span>
          <span
            className="font-mono text-gray-400 dark:text-gray-500 truncate"
            title={`${finding.file}:${finding.line}`}
          >
            {displayFile}:{finding.line}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-3">
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
            aria-label="Back to summary"
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

      {/* Unified diff view */}
      <UnifiedDiffView hunks={[hunk]} />
    </div>
  );
}
