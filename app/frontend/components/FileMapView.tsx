"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Finding } from "../types";
import { getJobSourceFile } from "../lib/api";

const SEVERITY_BG: Record<string, string> = {
  critical: "rgba(220,38,38,0.25)",
  high: "rgba(234,88,12,0.22)",
  medium: "rgba(202,138,4,0.22)",
  low: "rgba(59,130,246,0.18)",
};

const SEVERITY_MINIMAP: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
};

interface Props {
  jobId: string;
  filePath: string;
  findings: Finding[];
}

export function FileMapView({ jobId, filePath, findings }: Props) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedPath, setLoadedPath] = useState<string>("");
  // Which line number has its inline diff expanded (null = none)
  const [expandedLine, setExpandedLine] = useState<number | null>(null);
  const [hoveredFinding, setHoveredFinding] = useState<Finding | null>(null);
  const codeRef = useRef<HTMLDivElement>(null);
  const minimapRef = useRef<HTMLDivElement>(null);

  // Suppress stale expanded line if the loaded path doesn't match the requested path yet
  const effectiveLine = loadedPath === filePath ? expandedLine : null;

  useEffect(() => {
    let cancelled = false;
    getJobSourceFile(jobId, filePath)
      .then((data) => {
        if (!cancelled) {
          setLines(data.lines);
          setError(null);
          setLoadedPath(filePath);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e));
          setLines(null);
          setLoadedPath(filePath);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, filePath]);

  const isLoading = loadedPath !== filePath;

  // Map line â†’ findings on that line
  const findingsByLine = useMemo(() => {
    const map = new Map<number, Finding[]>();
    for (const f of findings) {
      const arr = map.get(f.line) ?? [];
      arr.push(f);
      map.set(f.line, arr);
    }
    return map;
  }, [findings]);

  // Sync minimap thumb with code-pane scroll position
  const syncThumb = useCallback(() => {
    const code = codeRef.current;
    const mini = minimapRef.current;
    if (!code || !mini) return;
    const { scrollTop, scrollHeight, clientHeight } = code;
    if (scrollHeight <= clientHeight) {
      // Everything fits â€” thumb fills the whole minimap
      mini.style.setProperty("--thumb-top", "0px");
      mini.style.setProperty("--thumb-height", `${mini.clientHeight}px`);
      return;
    }
    const ratio = scrollTop / (scrollHeight - clientHeight);
    const thumbH = (clientHeight / scrollHeight) * mini.clientHeight;
    const thumbT = ratio * (mini.clientHeight - thumbH);
    mini.style.setProperty("--thumb-top", `${thumbT}px`);
    mini.style.setProperty("--thumb-height", `${thumbH}px`);
  }, []);

  // Initialise thumb once content is rendered
  useEffect(() => {
    if (lines) {
      // rAF ensures the DOM has painted with the new content
      const id = requestAnimationFrame(syncThumb);
      return () => cancelAnimationFrame(id);
    }
  }, [lines, syncThumb]);

  // Clicking the minimap scrolls the code view
  const handleMinimapClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const code = codeRef.current;
    const mini = minimapRef.current;
    if (!code || !mini) return;
    const rect = mini.getBoundingClientRect();
    const ratio = (e.clientY - rect.top) / rect.height;
    code.scrollTop = ratio * (code.scrollHeight - code.clientHeight);
  };

  const scrollToLine = (lineNo: number) => {
    const rowEl = codeRef.current?.querySelector<HTMLElement>(
      `[data-line="${lineNo}"]`,
    );
    rowEl?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const total = lines?.length ?? 0;

  return (
    <div className="flex flex-col gap-0 text-xs">
      {/* Loading / error states */}
      {isLoading && (
        <div className="flex items-center justify-center h-32 text-gray-400 dark:text-gray-600">
          <svg
            className="w-4 h-4 animate-spin mr-2"
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
              d="M4 12a8 8 0 018-8v8H4z"
            />
          </svg>
          Loading sourceâ€¦
        </div>
      )}

      {!isLoading && error && (
        <div className="px-4 py-6 text-center text-red-500 dark:text-red-400">
          Could not load source file.
          <span className="block text-gray-400 text-[10px] mt-1">{error}</span>
        </div>
      )}

      {!isLoading && lines && (
        /* Fixed-height flex row so minimap matches code-pane height exactly */
        <div
          className="flex h-[52vh] rounded-b-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
          style={{
            fontFamily:
              "'JetBrains Mono','Fira Code','Cascadia Code',ui-monospace,monospace",
          }}
        >
          {/* â”€â”€ Code pane â”€â”€ */}
          <div
            ref={codeRef}
            onScroll={syncThumb}
            className="flex-1 overflow-auto h-full"
          >
            <table className="w-full border-collapse">
              <colgroup>
                <col style={{ width: "3rem" }} />
                <col />
              </colgroup>
              <tbody>
                {lines.map((content, idx) => {
                  const lineNo = idx + 1;
                  const lineFindings = findingsByLine.get(lineNo);
                  const worstSeverity = lineFindings?.[0]?.severity;
                  const isExpanded = effectiveLine === lineNo;
                  const isHovered =
                    hoveredFinding !== null &&
                    lineFindings?.includes(hoveredFinding);

                  const rowBg = isHovered
                    ? "rgba(99,102,241,0.15)"
                    : worstSeverity
                      ? SEVERITY_BG[worstSeverity]
                      : undefined;

                  return (
                    <>
                      {/* â”€â”€ Source line â”€â”€ */}
                      <tr
                        key={`l-${lineNo}`}
                        data-line={lineNo}
                        style={{ backgroundColor: rowBg }}
                        className={lineFindings ? "cursor-pointer" : undefined}
                        onClick={() => {
                          if (!lineFindings) return;
                          setExpandedLine(isExpanded ? null : lineNo);
                          if (!isExpanded) scrollToLine(lineNo);
                        }}
                      >
                        <td className="px-2 py-[1px] text-right select-none text-gray-400 dark:text-gray-600 border-r border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/60">
                          {lineNo}
                        </td>
                        <td className="px-3 py-[1px] whitespace-pre text-gray-800 dark:text-gray-200 text-[11px]">
                          {content || " "}
                          {lineFindings && (
                            <span className="ml-3 text-[10px] select-none opacity-50">
                              {isExpanded ? "â–˛" : "â–Ľ"}{" "}
                              {lineFindings.map((f) => f.rule_id).join(", ")}
                            </span>
                          )}
                        </td>
                      </tr>

                      {/* â”€â”€ Inline diff rows (shown when expanded) â”€â”€ */}
                      {isExpanded &&
                        lineFindings!.map((f, fi) => (
                          <>
                            {/* Annotation bar */}
                            <tr
                              key={`ann-${lineNo}-${fi}`}
                              className="select-none"
                            >
                              <td
                                colSpan={2}
                                className="px-3 py-0.5 bg-gray-100 dark:bg-gray-800 border-y border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 italic text-[10px]"
                              >
                                âš‘&nbsp;
                                <span className="font-semibold not-italic capitalize">
                                  {f.severity}
                                </span>
                                {" Â· "}
                                <span className="font-mono">{f.rule_id}</span>
                                {" Â· "}
                                {f.message}
                              </td>
                            </tr>
                            {/* Removed line */}
                            <tr
                              key={`del-${lineNo}-${fi}`}
                              style={{ backgroundColor: "rgba(255,0,0,0.08)" }}
                            >
                              <td className="px-2 py-0.5 text-right select-none text-red-400 dark:text-red-500 border-r border-red-200 dark:border-red-800 bg-red-50/60 dark:bg-red-900/20 font-mono">
                                â’
                              </td>
                              <td className="px-3 py-0.5 text-red-700 dark:text-red-300 line-through whitespace-pre text-[11px]">
                                {content || " "}
                              </td>
                            </tr>
                            {/* Added lines (suggestion) */}
                            {f.suggestion
                              .split("\n")
                              .filter((l) => l.trim())
                              .map((sugg, si) => (
                                <tr
                                  key={`add-${lineNo}-${fi}-${si}`}
                                  style={{
                                    backgroundColor: "rgba(0,180,0,0.08)",
                                  }}
                                >
                                  <td className="px-2 py-0.5 text-right select-none text-green-500 dark:text-green-400 border-r border-green-200 dark:border-green-800 bg-green-50/60 dark:bg-green-900/20 font-mono">
                                    +
                                  </td>
                                  <td className="px-3 py-0.5 text-green-800 dark:text-green-300 whitespace-pre-wrap text-[11px]">
                                    {sugg}
                                  </td>
                                </tr>
                              ))}
                          </>
                        ))}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* â”€â”€ Minimap sidebar â”€â”€ */}
          <div
            ref={minimapRef}
            onClick={handleMinimapClick}
            className="relative w-10 h-full shrink-0 bg-gray-50 dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 cursor-pointer overflow-hidden"
            title="Click to jump"
            style={
              {
                "--thumb-top": "0px",
                "--thumb-height": "40px",
              } as React.CSSProperties
            }
          >
            {/* Viewport thumb */}
            <div
              className="absolute left-0 right-0 bg-indigo-200/40 dark:bg-indigo-600/20 border-y border-indigo-300 dark:border-indigo-600 pointer-events-none"
              style={{ top: "var(--thumb-top)", height: "var(--thumb-height)" }}
            />

            {/* Finding markers â€” use pointer-events-auto so hover works */}
            {total > 0 &&
              findings.map((f, i) => {
                const pct = ((f.line - 1) / total) * 100;
                return (
                  <div
                    key={i}
                    className="absolute left-1 right-1 h-[3px] rounded-sm"
                    style={{
                      top: `${pct}%`,
                      backgroundColor:
                        SEVERITY_MINIMAP[f.severity] ?? "#6b7280",
                    }}
                    onMouseEnter={() => setHoveredFinding(f)}
                    onMouseLeave={() => setHoveredFinding(null)}
                  />
                );
              })}
          </div>
        </div>
      )}

      {!isLoading && lines && total > 0 && (
        <p className="text-[10px] text-gray-400 dark:text-gray-600 text-right pr-1 pt-0.5">
          {total} lines Â· {findings.length} finding
          {findings.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
