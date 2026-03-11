"use client";

export type DiffLineType = "context" | "del" | "add";

export interface DiffLine {
  type: DiffLineType;
  /** Line number in the "before" file; null for pure additions. */
  oldNo: number | null;
  /** Line number in the "after" file; null for pure deletions. */
  newNo: number | null;
  content: string;
}

export interface DiffHunk {
  /** Standard unified-diff header, e.g. "@@ -14,6 +14,9 @@ func_name" */
  header: string;
  lines: DiffLine[];
}

interface Props {
  hunks: DiffHunk[];
}

export function UnifiedDiffView({ hunks }: Props) {
  if (hunks.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-xs"
      style={{
        fontFamily:
          "'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace",
      }}
    >
      <table className="w-full border-collapse">
        <colgroup>
          {/* old line no */}
          <col style={{ width: "2.5rem" }} />
          {/* new line no */}
          <col style={{ width: "2.5rem" }} />
          {/* +/- sign */}
          <col style={{ width: "1.25rem" }} />
          {/* content */}
          <col />
        </colgroup>

        {hunks.map((hunk, hi) => (
          <tbody key={hi}>
            {/* Hunk divider bar */}
            <tr>
              <td
                colSpan={4}
                className="py-1 px-3 bg-[#dbeafe] dark:bg-[#1e3a5f] border-y border-[#93c5fd] dark:border-[#1d4ed8] select-none"
              >
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-px bg-[#93c5fd] dark:bg-[#1d4ed8]" />
                  <span className="text-[#3b82f6] dark:text-[#60a5fa] font-mono text-[11px]">
                    {hunk.header}
                  </span>
                  <div className="flex-1 h-px bg-[#93c5fd] dark:bg-[#1d4ed8]" />
                </div>
              </td>
            </tr>

            {/* Lines */}
            {hunk.lines.map((line, li) => {
              const isDel = line.type === "del";
              const isAdd = line.type === "add";

              const sign = isDel ? "−" : isAdd ? "+" : " ";
              const signColor = isDel
                ? "text-red-500 dark:text-red-400"
                : isAdd
                  ? "text-green-600 dark:text-green-400"
                  : "text-gray-400 dark:text-gray-600";
              const textColor = isDel
                ? "text-red-800 dark:text-red-300"
                : isAdd
                  ? "text-green-800 dark:text-green-300"
                  : "text-gray-700 dark:text-gray-300";
              const rowBg = isDel
                ? "rgba(255,0,0,0.08)"
                : isAdd
                  ? "rgba(0,200,0,0.08)"
                  : undefined;

              return (
                <tr key={li} style={{ backgroundColor: rowBg }}>
                  {/* Old line number */}
                  <td className="px-2 py-0.5 text-right text-gray-400 dark:text-gray-600 select-none border-r border-gray-200 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-900/50">
                    {line.oldNo ?? ""}
                  </td>
                  {/* New line number */}
                  <td className="px-2 py-0.5 text-right text-gray-400 dark:text-gray-600 select-none border-r border-gray-200 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-900/50">
                    {line.newNo ?? ""}
                  </td>
                  {/* +/- sign — unselectable so it doesn't interfere with copy-paste */}
                  <td
                    className={`px-0.5 py-0.5 text-center select-none font-semibold ${signColor}`}
                  >
                    {sign}
                  </td>
                  {/* Content — selectable */}
                  <td
                    className={`px-2 py-0.5 whitespace-pre-wrap break-words ${textColor}`}
                  >
                    {line.content || " "}
                  </td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );
}
