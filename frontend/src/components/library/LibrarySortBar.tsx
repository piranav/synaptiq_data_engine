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
    <div className="flex items-center justify-between mb-5">
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-surface text-sm text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all"
        >
          <span>Sort:</span>
          <span className="text-primary">{currentSortLabel}</span>
          <ChevronDown className={clsx("w-4 h-4 transition-transform", isDropdownOpen && "rotate-180")} />
        </button>

        {isDropdownOpen && (
          <div className="absolute top-full left-0 mt-2 w-40 rounded-lg overflow-hidden z-20 overlay-menu">
            {sortOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  onSortChange(option.value);
                  setIsDropdownOpen(false);
                }}
                className={clsx(
                  "w-full px-4 py-2.5 text-left text-sm border-b border-border-subtle last:border-b-0 transition-colors",
                  sort === option.value
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "text-secondary hover:bg-[var(--hover-bg)] hover:text-primary",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 p-1 rounded-lg border border-border bg-surface">
        <button
          onClick={() => onViewChange("grid")}
          className={clsx(
            "p-2 rounded-md transition-all border",
            view === "grid"
              ? "border-accent/30 bg-[var(--accent-soft)] text-[var(--accent)]"
              : "border-transparent text-secondary hover:text-primary hover:bg-[var(--hover-bg)]",
          )}
          title="Grid view"
        >
          <LayoutGrid className="w-4 h-4" />
        </button>
        <button
          onClick={() => onViewChange("list")}
          className={clsx(
            "p-2 rounded-md transition-all border",
            view === "list"
              ? "border-accent/30 bg-[var(--accent-soft)] text-[var(--accent)]"
              : "border-transparent text-secondary hover:text-primary hover:bg-[var(--hover-bg)]",
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
