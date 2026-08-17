"use client";

import { Bell } from "lucide-react";

interface HeaderProps {
  userName?: string;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);

  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export default function Header({
  userName = "Asif Khan",
}: HeaderProps) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <p className="text-sm font-semibold text-blue-600">
          Data Agent
        </p>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="Notifications"
          className="relative rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        >
          <Bell className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-2 border-l border-slate-200 pl-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
            {getInitials(userName)}
          </div>

          <span className="hidden text-sm font-medium text-slate-700 sm:block">
            {userName}
          </span>
        </div>
      </div>
    </header>
  );
}
