"use client";

import { Search, Plus, Command } from "lucide-react";

interface LibraryHeaderProps {
  onSearch: (query: string) => void;
  onAdd: () => void;
  searchQuery: string;
}

export function LibraryHeader({ onSearch, onAdd, searchQuery }: LibraryHeaderProps) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-7">
      <div>
        <h1 className="text-title-2 font-semibold tracking-tight text-primary">Library</h1>
        <p className="text-body-small text-secondary mt-1">Manage ingested sources and processing state.</p>
      </div>

      <div className="flex items-center gap-2.5">
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-elevated text-secondary text-xs">
          <Command className="w-3 h-3" />
          <span>K</span>
        </div>

        <div className="relative flex-1 min-w-0 md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary" />
          <input
            type="text"
            placeholder="Search library..."
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full h-10 pl-9 pr-4 bg-surface border border-border rounded-lg text-sm text-primary placeholder:text-secondary outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/18 transition-all"
          />
        </div>

        <button
          onClick={onAdd}
          className="inline-flex items-center gap-2 h-10 px-4 rounded-lg border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] hover:bg-[var(--hover-bg)] transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm font-medium">Add</span>
        </button>
      </div>
    </div>
  );
}
