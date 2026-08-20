"use client";

import { useCallback, useState, type ReactNode } from "react";

import GlobalSearch, {
  useGlobalSearchShortcut,
} from "@/components/global-search";
import AnnouncementBar from "@/components/navigation/AnnouncementBar";
import GlobalHeader from "@/components/navigation/GlobalHeader";

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const openSearch = useCallback(() => setSearchOpen(true), []);
  useGlobalSearchShortcut(openSearch);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <AnnouncementBar />
      <GlobalHeader onOpenSearch={openSearch} />
      <main className="min-h-0 flex-1 overflow-y-auto bg-background">
        {children}
      </main>
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
