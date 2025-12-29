"use client";

import { useMemo } from "react";
import { Link2, CornerDownRight, List, Sparkles, Loader2 } from "lucide-react";
import { ConceptPillList } from "./ConceptPill";

interface NotesRightPanelProps {
    linkedConcepts: string[];
    backlinks?: { id: string; title: string; preview?: string }[];
    headings?: { level: number; text: string }[];
    onConceptClick?: (concept: string) => void;
    onBacklinkClick?: (noteId: string) => void;
    onAddAsInsight?: () => void;
    isExtractingConcepts?: boolean;
    className?: string;
}

export function NotesRightPanel({
    linkedConcepts,
    backlinks = [],
    headings = [],
    onConceptClick,
    onBacklinkClick,
    onAddAsInsight,
    isExtractingConcepts = false,
    className = "",
}: NotesRightPanelProps) {
    // Filter headings to only show H1, H2, H3
    const tableOfContents = useMemo(() => {
        return headings.filter((h) => h.level <= 3);
    }, [headings]);

    return (
        <aside className={`w-64 shrink-0 border-l border-white/10 bg-black/20 overflow-y-auto ${className}`}>
            <div className="p-4 space-y-6">
                {/* Add as Insight Button */}
                {onAddAsInsight && (
                    <button
                        onClick={onAddAsInsight}
                        disabled={isExtractingConcepts}
                        className={`w-full h-9 rounded-md border border-accent/30 bg-accent/10 text-accent text-[13px] font-medium flex items-center justify-center gap-2 transition-colors ${isExtractingConcepts
                                ? 'opacity-70 cursor-not-allowed'
                                : 'hover:bg-accent/20'
                            }`}
                    >
                        {isExtractingConcepts ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Extracting...
                            </>
                        ) : (
                            <>
                                <Sparkles className="h-4 w-4" />
                                Add as Insight
                            </>
                        )}
                    </button>
                )}

                {/* Linked Concepts */}
                <div className="rounded-lg border border-white/10 bg-white/[0.02] overflow-hidden">
                    <div className="p-3 border-b border-white/10 flex items-center gap-2">
                        <Link2 className="h-4 w-4 text-white/50" strokeWidth={1.5} />
                        <span className="text-[12px] text-white/70 font-medium">Linked Concepts</span>
                        {isExtractingConcepts && (
                            <Loader2 className="h-3 w-3 animate-spin text-white/40 ml-auto" />
                        )}
                    </div>
                    <div className="p-3">
                        {linkedConcepts.length > 0 ? (
                            <ConceptPillList
                                concepts={linkedConcepts}
                                onConceptClick={onConceptClick}
                            />
                        ) : (
                            <p className="text-[12px] text-white/40 text-center py-2">
                                {isExtractingConcepts
                                    ? "Extracting concepts..."
                                    : "No concepts linked. Use [[concept]] to link."}
                            </p>
                        )}
                    </div>
                </div>

                {/* Backlinks */}
                {backlinks.length > 0 && (
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] overflow-hidden">
                        <div className="p-3 border-b border-white/10 flex items-center gap-2">
                            <CornerDownRight className="h-4 w-4 text-white/50" strokeWidth={1.5} />
                            <span className="text-[12px] text-white/70 font-medium">Backlinks</span>
                            <span className="ml-auto text-[11px] text-white/40">{backlinks.length}</span>
                        </div>
                        <div className="p-2 space-y-1">
                            {backlinks.map((link) => (
                                <button
                                    key={link.id}
                                    onClick={() => onBacklinkClick?.(link.id)}
                                    className="w-full text-left p-2 rounded-md hover:bg-white/[0.05] transition-colors"
                                >
                                    <p className="text-[13px] text-white/80 truncate">
                                        {link.title || "Untitled"}
                                    </p>
                                    {link.preview && (
                                        <p className="text-[11px] text-white/40 truncate mt-0.5">
                                            {link.preview}
                                        </p>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Table of Contents */}
                {tableOfContents.length > 0 && (
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] overflow-hidden">
                        <div className="p-3 border-b border-white/10 flex items-center gap-2">
                            <List className="h-4 w-4 text-white/50" strokeWidth={1.5} />
                            <span className="text-[12px] text-white/70 font-medium">Outline</span>
                        </div>
                        <div className="p-3 space-y-1">
                            {tableOfContents.map((heading, idx) => (
                                <button
                                    key={idx}
                                    className={`
                                        w-full text-left text-[12px] py-1 rounded
                                        hover:text-white transition-colors
                                        ${heading.level === 1
                                            ? "text-white/80 font-medium"
                                            : heading.level === 2
                                                ? "text-white/60 pl-3"
                                                : "text-white/40 pl-6"
                                        }
                                    `}
                                >
                                    {heading.text}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Note Info */}
                <div className="text-center text-[11px] text-white/30">
                    <p>Auto-saved</p>
                </div>
            </div>
        </aside>
    );
}
