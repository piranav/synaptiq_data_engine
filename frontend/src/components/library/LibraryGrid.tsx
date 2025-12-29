"use client";

import { Library, Loader2 } from "lucide-react";
import clsx from "clsx";
import { LibraryItem } from "@/lib/api/library";
import { LibraryCard } from "./LibraryCard";

interface LibraryGridProps {
    items: LibraryItem[];
    viewMode: "grid" | "list";
    isLoading: boolean;
    onOpen: (item: LibraryItem) => void;
    onDelete: (item: LibraryItem) => void;
    onReprocess?: (item: LibraryItem) => void;
    onAddSource: () => void;
}

export function LibraryGrid({
    items,
    viewMode,
    isLoading,
    onOpen,
    onDelete,
    onReprocess,
    onAddSource,
}: LibraryGridProps) {
    // Loading state
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 className="w-8 h-8 animate-spin text-white/40" />
            </div>
        );
    }

    // Empty state
    if (items.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-16 h-16 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center mb-6">
                    <Library className="w-8 h-8 text-accent" strokeWidth={1.5} />
                </div>
                <h2
                    className="text-[24px] font-semibold text-white mb-2"
                    style={{ fontFamily: "'SF Pro Display', sans-serif" }}
                >
                    Your library is empty
                </h2>
                <p className="text-[13px] text-white/60 max-w-md mb-6">
                    Start adding sources to build your knowledge base. Import videos, articles, notes, and files to extract concepts.
                </p>
                <button
                    onClick={onAddSource}
                    className="h-10 px-6 bg-accent hover:bg-accent/80 text-white rounded-lg text-[13px] font-medium transition-colors"
                >
                    Add your first source
                </button>
            </div>
        );
    }

    // Grid / List view
    return (
        <div
            className={clsx(
                "gap-4",
                viewMode === "grid"
                    ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                    : "flex flex-col"
            )}
        >
            {items.map((item) => (
                <LibraryCard
                    key={item.id}
                    item={item}
                    viewMode={viewMode}
                    onOpen={onOpen}
                    onDelete={onDelete}
                    onReprocess={onReprocess}
                />
            ))}
        </div>
    );
}
