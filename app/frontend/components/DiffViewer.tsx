"use client";

import { useState } from "react";
import { downloadModifiedFile, downloadAllAsZip } from "../lib/download";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface FileDiff {
  filename: string;
  /** Full text of the original file */
  original: string;
  /** Full text of the modified file */
  modified: string;
}

export interface DiffStats {
  added: number;
  removed: number;
}

type LineType = "unchanged" | "added" | "removed";

interface DiffLine {
  type: LineType;
  content: string;
}

interface ContextLine {
  kind: "line";
  type: LineType;
  content: string;
  origNum: number | null;
  modNum: number | null;
}

interface CollapseMarker {
  kind: "collapse";
  count: number;
}

type DisplayLine = ContextLine | CollapseMarker;

// ── LCS-based diff algorithm ───────────────────────────────────────────────────

export function computeDiff(original: string, modified: string): DiffLine[] {
  const a = original.split("\n");
  const b = modified.split("\n");
  const n = a.length;
  const m = b.length;

  // Build LCS DP table
  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    new Array(m + 1).fill(0),
  );
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to produce diff
  const result: DiffLine[] = [];
  let i = n;
  let j = m;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.unshift({ type: "unchanged", content: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: "added", content: b[j - 1] });
      j--;
    } else {
      result.unshift({ type: "removed", content: a[i - 1] });
      i--;
    }
  }
  return result;
}

export function diffStats(original: string, modified: string): DiffStats {
  const lines = computeDiff(original, modified);
  return {
    added: lines.filter((l) => l.type === "added").length,
    removed: lines.filter((l) => l.type === "removed").length,
  };
}

// ── Context collapse ───────────────────────────────────────────────────────────

const CONTEXT = 3; // unchanged lines to keep around each change

function buildDisplay(lines: DiffLine[]): DisplayLine[] {
  // Assign line numbers
  let origNum = 0;
  let modNum = 0;
  const numbered: ContextLine[] = lines.map((l) => {
    const on = l.type !== "added" ? origNum + 1 : null;
    const mn = l.type !== "removed" ? modNum + 1 : null;
    if (l.type !== "added") origNum++;
    if (l.type !== "removed") modNum++;
    return {
      kind: "line",
      type: l.type,
      content: l.content,
      origNum: on,
      modNum: mn,
    };
  });

  // Mark which lines are visible (changed ± CONTEXT)
  const visible = new Set<number>();
  numbered.forEach((l, idx) => {
    if (l.type !== "unchanged") {
      for (
        let k = Math.max(0, idx - CONTEXT);
        k <= Math.min(numbered.length - 1, idx + CONTEXT);
        k++
      ) {
        visible.add(k);
      }
    }
  });

  // All lines unchanged — collapse everything if long
  if (visible.size === 0) {
    return numbered.length > CONTEXT * 2
      ? [{ kind: "collapse", count: numbered.length }]
      : numbered;
  }

  const result: DisplayLine[] = [];
  let idx = 0;
  while (idx < numbered.length) {
    if (visible.has(idx)) {
      result.push(numbered[idx]);
      idx++;
    } else {
      let count = 0;
      while (idx < numbered.length && !visible.has(idx)) {
        count++;
        idx++;
      }
      result.push({ kind: "collapse", count });
    }
  }
  return result;
}

// ── FileDiffBlock ─────────────────────────────────────────────────────────────

function FileDiffBlock({
  diff,
  defaultOpen = true,
}: {
  diff: FileDiff;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const lines = computeDiff(diff.original, diff.modified);
  const added = lines.filter((l) => l.type === "added").length;
  const removed = lines.filter((l) => l.type === "removed").length;
  const display = buildDisplay(lines);

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden font-mono text-xs">
      {/* Header — div instead of button to avoid nested-button hydration error */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) =>
          e.key === "Enter" || e.key === " " ? setOpen((o) => !o) : undefined
        }
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-100 dark:bg-gray-900/60 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors cursor-pointer select-none"
      >
        <span className="font-semibold text-gray-700 dark:text-gray-200 text-sm font-sans">
          {diff.filename}
        </span>
        <div className="flex items-center gap-3">
          {added > 0 && (
            <span className="text-green-600 dark:text-green-400 font-semibold">
              +{added}
            </span>
          )}
          {removed > 0 && (
            <span className="text-red-500 dark:text-red-400 font-semibold">
              −{removed}
            </span>
          )}
          <button
            type="button"
            title={`Download ${diff.filename}`}
            onClick={(e) => {
              e.stopPropagation();
              downloadModifiedFile(diff);
            }}
            className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-200 transition-colors px-1.5 py-0.5 rounded hover:bg-indigo-50 dark:hover:bg-indigo-900/30"
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
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${open ? "" : "-rotate-90"}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>

      {/* Diff body */}
      {open && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <tbody>
              {display.map((line, i) => {
                if (line.kind === "collapse") {
                  return (
                    <tr key={i} className="bg-blue-50 dark:bg-blue-900/10">
                      <td
                        colSpan={3}
                        className="px-4 py-1 text-blue-500 dark:text-blue-400 italic select-none font-sans text-xs"
                      >
                        ··· {line.count} unchanged line
                        {line.count !== 1 ? "s" : ""} ···
                      </td>
                    </tr>
                  );
                }

                const bg =
                  line.type === "added"
                    ? "bg-green-50 dark:bg-green-900/20"
                    : line.type === "removed"
                      ? "bg-red-50 dark:bg-red-900/20"
                      : "bg-white dark:bg-gray-800";

                const textColor =
                  line.type === "added"
                    ? "text-green-800 dark:text-green-300"
                    : line.type === "removed"
                      ? "text-red-800 dark:text-red-400"
                      : "text-gray-700 dark:text-gray-300";

                const sigil =
                  line.type === "added"
                    ? "+"
                    : line.type === "removed"
                      ? "−"
                      : " ";

                return (
                  <tr key={i} className={bg}>
                    <td className="select-none w-10 px-2 text-right text-gray-400 dark:text-gray-600 border-r border-gray-200 dark:border-gray-700 leading-5">
                      {line.origNum ?? ""}
                    </td>
                    <td className="select-none w-10 px-2 text-right text-gray-400 dark:text-gray-600 border-r border-gray-200 dark:border-gray-700 leading-5">
                      {line.modNum ?? ""}
                    </td>
                    <td
                      className={`px-3 py-0.5 whitespace-pre leading-5 ${textColor}`}
                    >
                      <span className="select-none mr-2 opacity-60">
                        {sigil}
                      </span>
                      {line.content}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── DiffViewer ─────────────────────────────────────────────────────────────────

export function DiffViewer({ diffs }: { diffs: FileDiff[] }) {
  if (diffs.length === 0) return null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => downloadAllAsZip(diffs)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors"
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
      </div>
      {diffs.map((diff, i) => (
        <FileDiffBlock key={diff.filename} diff={diff} defaultOpen={i === 0} />
      ))}
    </div>
  );
}
