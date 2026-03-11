"use client";

import { useTheme } from "../providers/ThemeProvider";
import { SubmitForm } from "../components/SubmitForm";

export default function Home() {
  const { theme } = useTheme();

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-gradient-to-br from-slate-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-300">
      {/* Fixed header */}
      <div className="flex-shrink-0 text-center py-6 px-4">
        <div className="flex items-center justify-center gap-3 mb-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
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

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 pb-8">
        <div className="max-w-2xl mx-auto">
          <SubmitForm />
        </div>
      </div>
    </div>
  );
}
