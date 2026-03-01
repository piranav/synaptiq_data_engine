"use client";

import { useState } from "react";
import type { Citation } from "@/lib/api/chat";

interface CitationChipProps {
  index: number;
  citation: Citation;
}

export function CitationChip({ index, citation }: CitationChipProps) {
  const [isOpen, setIsOpen] = useState(false);

  const getDisplayName = () => {
    if (citation.title) return citation.title;
    if (citation.source_title) return citation.source_title;
    return `Source ${index + 1}`;
  };

  const displayName = getDisplayName();
  const shortName = displayName.length > 20 ? displayName.substring(0, 17) + "..." : displayName;

  return (
    <span className="relative inline-block align-baseline">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="h-6 px-1.5 rounded border border-border text-[11px] leading-[16px] text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-colors"
      >
        {shortName}
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />

          <div className="absolute left-0 top-full mt-1 z-50 w-72 rounded-lg p-3 animate-in fade-in zoom-in-95 duration-150 overlay-menu">
            <div className="flex items-start gap-2">
              <span className="flex items-center justify-center min-w-[22px] h-[22px] text-[11px] font-medium bg-elevated text-primary rounded shrink-0 border border-border">
                {index + 1}
              </span>
              <div className="flex-1 min-w-0">
                <h4 className="text-[13px] leading-[18px] font-medium text-primary">{displayName}</h4>

                {citation.chunk_text && (
                  <p className="text-[12px] leading-[16px] text-secondary mt-2 line-clamp-3">{citation.chunk_text}</p>
                )}

                {(citation.url || citation.source_url) && (
                  <a
                    href={citation.url || citation.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[12px] leading-[16px] text-[var(--accent)] hover:underline mt-2"
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
