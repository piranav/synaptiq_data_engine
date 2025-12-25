"use client";

import { useState } from "react";
import clsx from "clsx";
import type { Citation } from "@/lib/api/chat";

interface CitationChipProps {
    index: number;
    citation: Citation;
}

export function CitationChip({ index, citation }: CitationChipProps) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <span className="relative inline-block">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="inline-flex items-center justify-center min-w-[22px] h-[18px] px-1.5 text-caption font-medium bg-accent/15 text-accent rounded hover:bg-accent/25 transition-colors"
            >
                [{index + 1}]
            </button>

            {/* Popover */}
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsOpen(false)}
                    />

                    {/* Popover content */}
                    <div className="absolute left-0 top-full mt-1 z-50 w-72 bg-elevated border border-border rounded-lg shadow-elevated p-3 animate-in fade-in zoom-in-95 duration-150">
                        <h4 className="text-body-small font-medium text-primary truncate">
                            {citation.title || citation.source_title || "Unknown Source"}
                        </h4>

                        {citation.chunk_text && (
                            <p className="text-callout text-secondary mt-2 line-clamp-3">
                                {citation.chunk_text}
                            </p>
                        )}

                        {(citation.url || citation.source_url) && (
                            <a
                                href={citation.url || citation.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-callout text-accent hover:underline mt-2"
                                onClick={(e) => e.stopPropagation()}
                            >
                                Open source →
                            </a>
                        )}
                    </div>
                </>
            )}
        </span>
    );
}
