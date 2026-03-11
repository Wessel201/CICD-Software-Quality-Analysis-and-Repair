"use client";

import Link from "next/link";
import { useTheme } from "../providers/ThemeProvider";
import { ThemeToggle } from "./ThemeToggle";

interface NavBarProps {
  /** Optional subtitle rendered below the title in smaller text */
  subtitle?: string;
}

export function NavBar({ subtitle }: NavBarProps) {
  const { theme } = useTheme();

  return (
    <div className="flex-shrink-0 px-4 pt-5 pb-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between">
          {/* Left: logo + title */}
          <Link
            href="/"
            className="flex items-center gap-3 group"
            aria-label="Go to home"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={theme === "dark" ? "/favicon.svg" : "/favicon-dark.svg"}
              alt="logo"
              className="w-9 h-9 transition-transform group-hover:scale-110"
            />
            <div className="flex flex-col leading-tight">
              <span className="text-2xl font-bold text-gray-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                Code Quality Analyzer
              </span>
              {subtitle && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {subtitle}
                </span>
              )}
            </div>
          </Link>

          {/* Right: theme toggle */}
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}
