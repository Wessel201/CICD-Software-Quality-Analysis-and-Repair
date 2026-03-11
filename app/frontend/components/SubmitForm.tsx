"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { createJob, mockCreateJob } from "../lib/api";

const ACCEPTED_EXTENSIONS = [".zip", ".py"];

function getFilesWarning(files: File[]): string | null {
  const hasZip = files.some((f) => f.name.toLowerCase().endsWith(".zip"));
  if (hasZip) {
    if (files.length > 1)
      return "When uploading a .zip, select only one file at a time.";
    return null;
  }
  const invalid = files.find(
    (f) =>
      !ACCEPTED_EXTENSIONS.includes(
        f.name.slice(f.name.lastIndexOf(".")).toLowerCase(),
      ),
  );
  if (invalid)
    return `"${invalid.name}" is not supported. Only .zip archives and .py files are accepted.`;
  return null;
}

export function SubmitForm() {
  const router = useRouter();

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [fileWarning, setFileWarning] = useState<string | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const pickFiles = (files: File[]) => {
    const warning = getFilesWarning(files);
    setFileWarning(warning);
    setSelectedFiles(warning ? [] : files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) pickFiles(files);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) pickFiles(files);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (fileWarning || submitting) return;

    setSubmitting(true);
    try {
      let job;
      const singleFile = selectedFiles.length === 1 ? selectedFiles[0] : null;
      try {
        if (selectedFiles.length > 1)
          throw new Error("Multiple .py files — skipping to mock");
        job = await createJob(singleFile, githubUrl);
      } catch (err) {
        console.warn(
          "[API] POST /api/v1/jobs failed, falling back to mock mode",
          err,
        );
        job = await mockCreateJob();
      }

      // Build filesParam
      let filesParam: string;
      if (githubUrl) {
        filesParam = "*";
      } else if (singleFile) {
        const ext = singleFile.name
          .slice(singleFile.name.lastIndexOf("."))
          .toLowerCase();
        filesParam =
          ext === ".zip"
            ? "*"
            : singleFile.name
                .replace(/\.py$/i, "")
                .replace(/_(original|modified)$/i, "");
      } else {
        // Multiple .py files — join their stems
        filesParam = selectedFiles
          .map((f) =>
            f.name.replace(/\.py$/i, "").replace(/_(original|modified)$/i, ""),
          )
          .join(",");
      }

      router.push(
        `/results/${job.job_id}?files=${encodeURIComponent(filesParam)}`,
      );
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = (selectedFiles.length > 0 && !fileWarning) || !!githubUrl;

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 flex flex-col gap-8 transition-colors"
    >
      {/* GitHub URL */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
          GitHub Repository URL
        </label>
        <input
          type="url"
          placeholder="https://github.com/username/repo"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
          disabled={submitting}
          className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-colors disabled:opacity-60"
        />
      </div>

      {/* Divider */}
      <div className="flex items-center gap-4">
        <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
        <span className="text-sm font-medium text-gray-400 dark:text-gray-500">
          or
        </span>
        <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
      </div>

      {/* File drop zone */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
          Upload Project Files
        </label>
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            fileWarning
              ? "border-red-400 dark:border-red-500 bg-red-50 dark:bg-red-900/10"
              : "border-indigo-300 dark:border-indigo-600 bg-indigo-50 dark:bg-gray-700 hover:border-indigo-500 dark:hover:border-indigo-400"
          }`}
        >
          <svg
            className={`w-12 h-12 mx-auto mb-3 ${fileWarning ? "text-red-400" : "text-indigo-400 dark:text-indigo-300"}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <div
            className={`font-medium text-sm ${fileWarning ? "text-red-600 dark:text-red-400" : "text-gray-600 dark:text-gray-300"}`}
          >
            {selectedFiles.length === 0 ? (
              <span>Click to select or drag and drop</span>
            ) : selectedFiles.length === 1 ? (
              <span className="font-mono">{selectedFiles[0].name}</span>
            ) : (
              <ul className="text-left space-y-0.5">
                {selectedFiles.map((f) => (
                  <li key={f.name} className="flex items-center gap-1.5">
                    <span className="text-indigo-400 text-xs">●</span>
                    <span className="font-mono">{f.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {selectedFiles.length === 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              .zip archive or one or more .py files
            </p>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,.py"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* File warning */}
      {fileWarning && (
        <p className="text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
          <svg
            className="w-4 h-4 shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
              clipRule="evenodd"
            />
          </svg>
          {fileWarning}
        </p>
      )}

      {/* Format hint */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
        <svg
          className="w-4 h-4 shrink-0 text-amber-500"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
            clipRule="evenodd"
          />
        </svg>
        <span className="text-xs text-amber-700 dark:text-amber-400">
          Only <strong>.zip</strong> archives and <strong>.py</strong> files are
          currently supported
        </span>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit || submitting}
        className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 ${
          canSubmit && !submitting
            ? "bg-indigo-600 dark:bg-indigo-500 text-white hover:bg-indigo-700 dark:hover:bg-indigo-600"
            : "bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed"
        }`}
      >
        {submitting && (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
        )}
        {submitting ? "Submitting…" : "Analyze Project"}
      </button>
    </form>
  );
}
