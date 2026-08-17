"use client";

import type { ReactNode } from "react";

import Header from "@/components/header";
import Sidebar from "@/components/sidebar";

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-full min-h-0">
      <Sidebar />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Header />

        <main className="min-h-0 flex-1 overflow-y-auto bg-slate-100">
          {children}
        </main>
      </div>
    </div>
  );
}
