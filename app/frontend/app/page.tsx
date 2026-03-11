"use client";

import { SubmitForm } from "../components/SubmitForm";
import { NavBar } from "../components/NavBar";
import { RecentJobs } from "../components/RecentJobs";

export default function Home() {
  return (
    <div className="h-screen overflow-hidden flex flex-col bg-gradient-to-br from-slate-50 to-blue-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-300">
      <NavBar subtitle="Upload your project and get AI-powered improvements" />

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto hide-scrollbar px-4 pb-8">
        <div className="max-w-2xl mx-auto">
          <SubmitForm />
          <RecentJobs />
        </div>
      </div>
    </div>
  );
}
