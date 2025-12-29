"use client";

import { Search, Plus, Command } from "lucide-react";

interface LibraryHeaderProps {
    onSearch: (query: string) => void;
    onAdd: () => void;
    searchQuery: string;
}

export function LibraryHeader({ onSearch, onAdd, searchQuery }: LibraryHeaderProps) {
    return (
        <div className="flex items-center justify-between mb-8">
            <h1
                className="text-[28px] font-semibold tracking-tight text-white"
                style={{ fontFamily: "'SF Pro Display', sans-serif" }}
            >
                Library
            </h1>

            <div className="flex items-center gap-3">
                {/* Command palette hint */}
                <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-white/40 text-xs">
                    <Command className="w-3 h-3" />
                    <span>K</span>
                </div>

                {/* Search input */}
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                        type="text"
                        placeholder="Search library..."
                        value={searchQuery}
                        onChange={(e) => onSearch(e.target.value)}
                        className="w-64 h-10 pl-9 pr-4 bg-white/[0.03] border border-white/10 rounded-lg text-sm text-white placeholder-white/40 outline-none focus:border-white/20 focus:bg-white/[0.05] transition-all"
                    />
                </div>

                {/* Add button */}
                <button
                    onClick={onAdd}
                    className="flex items-center gap-2 h-10 px-4 bg-accent hover:bg-accent/80 text-white rounded-lg text-sm font-medium transition-colors"
                >
                    <Plus className="w-4 h-4" />
                    <span>Add</span>
                </button>
            </div>
        </div>
    );
}
