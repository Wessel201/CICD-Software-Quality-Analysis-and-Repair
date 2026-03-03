"use client";

import { useState } from "react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"upload" | "github">("upload");
  const [fileName, setFileName] = useState<string>("");
  const [githubUrl, setGithubUrl] = useState<string>("");

  const handleZipSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFileName(e.target.files[0].name);
    }
  };

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Upload submitted for:", fileName);
    // Mock - does nothing yet
  };

  const handleGithubSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("GitHub submitted for:", githubUrl);
    // Mock - does nothing yet
  };

  return (
    <>
      <div className="min-h-screen bg-gradient-to-br from-blue-100 to-indigo-200 dark:from-gray-900 dark:to-gray-800 py-12 px-4 transition-colors duration-300">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-2">
              <img src="/favicon.svg" alt="logo" className="w-10 h-10" />
              <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
                Code Quality Analyzer
              </h1>
            </div>
            <p className="text-gray-600 dark:text-gray-300">
              Upload your project and get AI-powered improvements
            </p>
          </div>

          {/* Card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 transition-colors">
            {/* Tabs */}
            <div className="flex gap-4 mb-8 border-b border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setActiveTab("upload")}
                className={`pb-4 px-4 font-semibold transition-colors ${
                  activeTab === "upload"
                    ? "text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                }`}
              >
                Upload ZIP
              </button>
              <button
                onClick={() => setActiveTab("github")}
                className={`pb-4 px-4 font-semibold transition-colors ${
                  activeTab === "github"
                    ? "text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                }`}
              >
                GitHub Link
              </button>
            </div>

            {/* Upload Tab */}
            {activeTab === "upload" && (
              <form onSubmit={handleUploadSubmit}>
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
                    Select your project ZIP
                  </label>
                  <div
                    className="border-2 border-dashed border-indigo-300 dark:border-indigo-600 rounded-lg p-8 text-center hover:border-indigo-500 dark:hover:border-indigo-400 transition-colors cursor-pointer bg-indigo-50 dark:bg-gray-700"
                    onClick={() =>
                      document.getElementById("zip-input")?.click()
                    }
                  >
                    <svg
                      className="w-12 h-12 mx-auto mb-4 text-indigo-400 dark:text-indigo-300"
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
                    <p className="text-gray-600 dark:text-gray-300 font-medium">
                      {fileName
                        ? fileName
                        : "Click to select ZIP file or drag and drop"}
                    </p>
                  </div>
                  <input
                    id="zip-input"
                    type="file"
                    accept=".zip"
                    onChange={handleZipSelect}
                    className="hidden"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!fileName}
                  className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                    fileName
                      ? "bg-indigo-600 dark:bg-indigo-500 text-white hover:bg-indigo-700 dark:hover:bg-indigo-600"
                      : "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed"
                  }`}
                >
                  Analyze Project
                </button>
              </form>
            )}

            {/* GitHub Tab */}
            {activeTab === "github" && (
              <form onSubmit={handleGithubSubmit}>
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    GitHub Repository URL
                  </label>
                  <input
                    type="url"
                    placeholder="https://github.com/username/repo"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-colors"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Supports public repositories (private support coming soon)
                  </p>
                </div>
                <button
                  type="submit"
                  disabled={!githubUrl}
                  className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                    githubUrl
                      ? "bg-indigo-600 dark:bg-indigo-500 text-white hover:bg-indigo-700 dark:hover:bg-indigo-600"
                      : "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed"
                  }`}
                >
                  Analyze Repository
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
