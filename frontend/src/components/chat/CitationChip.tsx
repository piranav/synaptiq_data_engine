"use client";

import { useState } from "react";
import type { Citation } from "@/lib/api/chat";

interface CitationChipProps {
    index: number;
    citation: Citation;
}

export function CitationChip({ index, citation }: CitationChipProps) {
    const [isOpen, setIsOpen] = useState(false);

    // Get display name (author/source name)
    const getDisplayName = () => {
        if (citation.title) return citation.title;
        if (citation.source_title) return citation.source_title;
        return `Source ${index + 1}`;
    };

    // Truncate to reasonable length
    const displayName = getDisplayName();
    const shortName = displayName.length > 20
        ? displayName.substring(0, 17) + "..."
        : displayName;

    return (
        <span className="relative inline-block align-baseline">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="h-6 px-1.5 rounded border border-white/10 text-[11px] leading-[16px] text-white/70 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
                {shortName}
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
                    <div className="absolute left-0 top-full mt-1 z-50 w-72 rounded-lg border border-white/10 bg-[#0B0D12] shadow-[0_8px_24px_rgba(0,0,0,0.5)] p-3 animate-in fade-in zoom-in-95 duration-150">
                        <div className="flex items-start gap-2">
                            <span className="flex items-center justify-center min-w-[22px] h-[22px] text-[11px] font-medium bg-white/10 text-white/80 rounded shrink-0">
                                {index + 1}
                            </span>
                            <div className="flex-1 min-w-0">
                                <h4 className="text-[13px] leading-[18px] font-medium text-white">
                                    {displayName}
                                </h4>

                                {citation.chunk_text && (
                                    <p className="text-[12px] leading-[16px] text-white/60 mt-2 line-clamp-3">
                                        {citation.chunk_text}
                                    </p>
                                )}

                                {(citation.url || citation.source_url) && (
                                    <a
                                        href={citation.url || citation.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 text-[12px] leading-[16px] text-[#256BEE] hover:underline mt-2"
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        Open source →
                                    </a>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </span>
    );
}
