"use client";

import { useState } from "react";
import { useTheme } from "../providers/ThemeProvider";

const ACCEPTED_EXTENSIONS = [".zip", ".py"];

function getFileWarning(name: string): string | null {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `"${name}" is not supported. Only .zip archives and .py files are accepted.`;
  }
  return null;
}

export default function Home() {
  const { theme } = useTheme();
  const [fileName, setFileName] = useState<string>("");
  const [fileWarning, setFileWarning] = useState<string | null>(null);
  const [githubUrl, setGithubUrl] = useState<string>("");

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setFileWarning(getFileWarning(file.name));
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setFileWarning(getFileWarning(file.name));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (fileWarning) return;
    console.log("Submit:", { fileName, githubUrl });
    // Mock - does nothing yet
  };

  const canSubmit = (!!fileName && !fileWarning) || !!githubUrl;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 py-12 px-4 transition-colors duration-300">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <img
              src={theme === "dark" ? "/favicon.svg" : "/favicon-dark.svg"}
              alt="logo"
              className="w-10 h-10"
            />
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
              Code Quality Analyzer
            </h1>
          </div>
          <p className="text-gray-600 dark:text-gray-300">
            Upload your project and get AI-powered improvements
          </p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 flex flex-col gap-8 transition-colors"
        >
          {/* GitHub Section */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              GitHub Repository URL
            </label>
            <input
              type="url"
              placeholder="https://github.com/username/repo"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-colors"
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

          {/* File Upload Section */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Upload Project File
            </label>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => document.getElementById("file-input")?.click()}
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
              <p
                className={`font-medium text-sm ${fileWarning ? "text-red-600 dark:text-red-400" : "text-gray-600 dark:text-gray-300"}`}
              >
                {fileName ? fileName : "Click to select or drag and drop"}
              </p>
              {!fileName && (
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  .zip or .py
                </p>
              )}
            </div>

            <input
              id="file-input"
              type="file"
              accept=".zip,.py"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
          {/* File warning */}
          {fileWarning && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
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

          <div className="flex items-center gap-2 mt-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
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
              Only <strong>.zip</strong> archives and <strong>.py</strong> files
              are currently supported
            </span>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!canSubmit}
            className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
              canSubmit
                ? "bg-indigo-600 dark:bg-indigo-500 text-white hover:bg-indigo-700 dark:hover:bg-indigo-600"
                : "bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed"
            }`}
          >
            Analyze Project
          </button>
        </form>
      </div>
    </div>
  );
}
