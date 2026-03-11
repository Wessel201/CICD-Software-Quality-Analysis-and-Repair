import calculatorOriginal from "./original/calculator.py";
import calculatorModified from "./modified/calculator.py";
import utilsOriginal from "./original/utils.py";
import utilsModified from "./modified/utils.py";
import sorterOriginal from "./original/helpers/sorter.py";
import sorterModified from "./modified/helpers/sorter.py";
import type { FileDiff } from "../components/DiffViewer";

// Keyed by filename stem (no extension)
export const MOCK_DIFF_MAP: Record<string, FileDiff> = {
  calculator: {
    filename: "calculator.py",
    original: calculatorOriginal,
    modified: calculatorModified,
  },
  utils: {
    filename: "utils.py",
    original: utilsOriginal,
    modified: utilsModified,
  },
  sorter: {
    filename: "helpers/sorter.py",
    original: sorterOriginal,
    modified: sorterModified,
  },
};

/**
 * Return the relevant FileDiffs for a `files` URL param.
 * "*" or empty → all files.
 * Otherwise comma-separated stems, e.g. "calculator" or "calculator.py".
 * Subfolder files (e.g. "helpers/sorter") are matched by basename too.
 */
export function getDiffsForFiles(filesParam: string): FileDiff[] {
  if (!filesParam || filesParam === "*") {
    return Object.values(MOCK_DIFF_MAP);
  }
  return filesParam
    .split(",")
    .map((f) =>
      f
        .trim()
        .replace(/\.py$/i, "")
        .replace(/_(original|modified)$/i, ""),
    )
    .flatMap((stem) => {
      // Try exact key first
      const direct = MOCK_DIFF_MAP[stem];
      if (direct) return [direct];
      // Fall back to matching by basename (e.g. "sorter" matches "helpers/sorter.py")
      const basename = stem.split("/").pop() ?? stem;
      const byBasename = Object.values(MOCK_DIFF_MAP).find(
        (d) => d.filename.replace(/\.py$/i, "").split("/").pop() === basename,
      );
      return byBasename ? [byBasename] : [];
    });
}

// Convenience export of all diffs
export const MOCK_DIFFS = Object.values(MOCK_DIFF_MAP);
