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
        <div className="flex items-center gap-2 mb-6 pb-4 border-b border-white/10">
            {tabs.map((tab) => {
                const count = stats[tab.key] || 0;
                const isActive = activeTab === tab.key;

                return (
                    <button
                        key={tab.key}
                        onClick={() => onTabChange(tab.key)}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                            isActive
                                ? "bg-white/[0.08] text-white border border-white/10"
                                : "text-white/60 hover:text-white hover:bg-white/[0.04]"
                        )}
                    >
                        <span>{tab.label}</span>
                        <span
                            className={clsx(
                                "min-w-[24px] px-1.5 py-0.5 rounded-md text-[11px] font-medium text-center",
                                isActive
                                    ? "bg-accent/20 text-accent"
                                    : "bg-white/10 text-white/50"
                            )}
                        >
                            {count}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

export type { TabType };
