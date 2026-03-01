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
  const tableOfContents = useMemo(() => headings.filter((h) => h.level <= 3), [headings]);

  return (
    <aside className={`w-64 shrink-0 border-l border-border bg-surface/55 overflow-y-auto thin-scrollbar ${className}`}>
      <div className="p-4 space-y-6">
        {onAddAsInsight && (
          <button
            onClick={onAddAsInsight}
            disabled={isExtractingConcepts}
            className={`w-full h-9 rounded-md border border-accent/30 bg-[var(--accent-soft)] text-[var(--accent)] text-[13px] font-medium flex items-center justify-center gap-2 transition-colors ${
              isExtractingConcepts ? "opacity-70 cursor-not-allowed" : "hover:bg-[var(--hover-bg)]"
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

        <div className="rounded-lg border border-border bg-surface overflow-hidden">
          <div className="p-3 border-b border-border flex items-center gap-2">
            <Link2 className="h-4 w-4 text-secondary" strokeWidth={1.5} />
            <span className="text-[12px] text-secondary font-medium">Linked Concepts</span>
            {isExtractingConcepts && <Loader2 className="h-3 w-3 animate-spin text-secondary ml-auto" />}
          </div>
          <div className="p-3">
            {linkedConcepts.length > 0 ? (
              <ConceptPillList concepts={linkedConcepts} onConceptClick={onConceptClick} />
            ) : (
              <p className="text-[12px] text-secondary text-center py-2">
                {isExtractingConcepts ? "Extracting concepts..." : "No concepts linked. Use [[concept]] to link."}
              </p>
            )}
          </div>
        </div>

        {backlinks.length > 0 && (
          <div className="rounded-lg border border-border bg-surface overflow-hidden">
            <div className="p-3 border-b border-border flex items-center gap-2">
              <CornerDownRight className="h-4 w-4 text-secondary" strokeWidth={1.5} />
              <span className="text-[12px] text-secondary font-medium">Backlinks</span>
              <span className="ml-auto text-[11px] text-tertiary">{backlinks.length}</span>
            </div>
            <div className="p-2 space-y-1">
              {backlinks.map((link) => (
                <button
                  key={link.id}
                  onClick={() => onBacklinkClick?.(link.id)}
                  className="w-full text-left p-2 rounded-md hover:bg-[var(--hover-bg)] transition-colors"
                >
                  <p className="text-[13px] text-primary truncate">{link.title || "Untitled"}</p>
                  {link.preview && <p className="text-[11px] text-secondary truncate mt-0.5">{link.preview}</p>}
                </button>
              ))}
            </div>
          </div>
        )}

        {tableOfContents.length > 0 && (
          <div className="rounded-lg border border-border bg-surface overflow-hidden">
            <div className="p-3 border-b border-border flex items-center gap-2">
              <List className="h-4 w-4 text-secondary" strokeWidth={1.5} />
              <span className="text-[12px] text-secondary font-medium">Outline</span>
            </div>
            <div className="p-3 space-y-1">
              {tableOfContents.map((heading, idx) => (
                <button
                  key={idx}
                  className={`
                    w-full text-left text-[12px] py-1 rounded hover:text-primary transition-colors
                    ${
                      heading.level === 1
                        ? "text-primary font-medium"
                        : heading.level === 2
                          ? "text-secondary pl-3"
                          : "text-tertiary pl-6"
                    }
                  `}
                >
                  {heading.text}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="text-center text-[11px] text-tertiary">
          <p>Auto-saved</p>
        </div>
      </div>
    </aside>
  );
}
