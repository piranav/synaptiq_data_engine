"use client";

import { LayoutGrid, List, ChevronDown } from "lucide-react";
import clsx from "clsx";
import { useState, useRef, useEffect } from "react";

type SortOption = "recent" | "oldest" | "alphabetical";
type ViewMode = "grid" | "list";

interface LibrarySortBarProps {
    sort: SortOption;
    view: ViewMode;
    onSortChange: (sort: SortOption) => void;
    onViewChange: (view: ViewMode) => void;
}

const sortOptions: { value: SortOption; label: string }[] = [
    { value: "recent", label: "Recent" },
    { value: "oldest", label: "Oldest" },
    { value: "alphabetical", label: "Alphabetical" },
];

export function LibrarySortBar({ sort, view, onSortChange, onViewChange }: LibrarySortBarProps) {
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const currentSortLabel = sortOptions.find((o) => o.value === sort)?.label || "Recent";

    return (
        <div className="flex items-center justify-between mb-6">
            {/* Sort dropdown */}
            <div className="relative" ref={dropdownRef}>
                <button
                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/10 text-sm text-white/70 hover:text-white hover:bg-white/[0.05] hover:border-white/20 transition-all"
                >
                    <span>Sort:</span>
                    <span className="text-white">{currentSortLabel}</span>
                    <ChevronDown className={clsx("w-4 h-4 transition-transform", isDropdownOpen && "rotate-180")} />
                </button>

                {isDropdownOpen && (
                    <div className="absolute top-full left-0 mt-2 w-40 bg-[#1C1C1E] border border-white/10 rounded-lg shadow-lg overflow-hidden z-20">
                        {sortOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => {
                                    onSortChange(option.value);
                                    setIsDropdownOpen(false);
                                }}
                                className={clsx(
                                    "w-full px-4 py-2.5 text-left text-sm transition-colors",
                                    sort === option.value
                                        ? "bg-accent/20 text-accent"
                                        : "text-white/70 hover:bg-white/[0.06] hover:text-white"
                                )}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* View toggle */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.03] border border-white/10">
                <button
                    onClick={() => onViewChange("grid")}
                    className={clsx(
                        "p-2 rounded-md transition-all",
                        view === "grid"
                            ? "bg-white/[0.08] text-white"
                            : "text-white/50 hover:text-white hover:bg-white/[0.04]"
                    )}
                    title="Grid view"
                >
                    <LayoutGrid className="w-4 h-4" />
                </button>
                <button
                    onClick={() => onViewChange("list")}
                    className={clsx(
                        "p-2 rounded-md transition-all",
                        view === "list"
                            ? "bg-white/[0.08] text-white"
                            : "text-white/50 hover:text-white hover:bg-white/[0.04]"
                    )}
                    title="List view"
                >
                    <List className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}

export type { SortOption, ViewMode };
