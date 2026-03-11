import type { FileDiff } from "../components/DiffViewer";

/** Trigger a browser download of the modified content of a single file. */
export function downloadModifiedFile(diff: FileDiff): void {
  const blob = new Blob([diff.modified], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  // Use only the basename so the browser saves as e.g. "sorter.py", not "helpers/sorter.py"
  a.download = diff.filename.split("/").pop() ?? diff.filename;
  a.href = url;
  a.click();
  URL.revokeObjectURL(url);
}

/** Zip all modified files and trigger a download of the zip, preserving subfolder paths. */
export async function downloadAllAsZip(
  diffs: FileDiff[],
  zipName = "modified-files.zip",
): Promise<void> {
  const { default: JSZip } = await import("jszip");
  const zip = new JSZip();
  for (const diff of diffs) {
    zip.file(diff.filename, diff.modified);
  }
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.download = zipName;
  a.href = url;
  a.click();
  URL.revokeObjectURL(url);
}
