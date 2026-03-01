"use client";

import clsx from "clsx";
import { LibraryStats } from "@/lib/api/library";

type TabType = "all" | "videos" | "articles" | "notes" | "files";

interface LibraryTabsProps {
  activeTab: TabType;
  stats: LibraryStats;
  onTabChange: (tab: TabType) => void;
}

const tabs: { key: TabType; label: string }[] = [
  { key: "all", label: "All" },
  { key: "videos", label: "Videos" },
  { key: "articles", label: "Articles" },
  { key: "notes", label: "Notes" },
  { key: "files", label: "Files" },
];

export function LibraryTabs({ activeTab, stats, onTabChange }: LibraryTabsProps) {
  return (
    <div className="mb-6 overflow-x-auto no-scrollbar">
      <div className="inline-flex items-center gap-2 min-w-max rounded-xl border border-border bg-surface p-1.5">
        {tabs.map((tab) => {
          const count = stats[tab.key] || 0;
          const isActive = activeTab === tab.key;

          return (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={clsx(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all border",
                isActive
                  ? "border-accent/30 bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "border-transparent text-secondary hover:text-primary hover:bg-[var(--hover-bg)]",
              )}
            >
              <span>{tab.label}</span>
              <span
                className={clsx(
                  "min-w-[24px] px-1.5 py-0.5 rounded-md text-[11px] font-medium text-center border",
                  isActive ? "border-accent/35 bg-accent/18 text-[var(--accent)]" : "border-border bg-elevated text-secondary",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { TabType };
