"use client";

import { SWISS_COLORS, RELATIONSHIP_LABELS } from "@/lib/graph/adapter";

interface GraphLegendProps {
  className?: string;
  compact?: boolean;
}

export function GraphLegend({ className = "", compact = false }: GraphLegendProps) {
  const nodeTypes = [
    { label: "Concept", color: SWISS_COLORS.concept },
    { label: "Definition", color: SWISS_COLORS.definition },
    { label: "Source", color: SWISS_COLORS.source },
  ];

  const sourceTypes = [
    { label: "YouTube", color: SWISS_COLORS.youtube },
    { label: "Article", color: SWISS_COLORS.web_article },
    { label: "Note", color: SWISS_COLORS.note },
    { label: "PDF", color: SWISS_COLORS.pdf },
  ];

  const relationships = Object.entries(RELATIONSHIP_LABELS).slice(0, 4).map(([type, label]) => ({ type, label }));

  if (compact) {
    return (
      <div className={`flex items-center gap-3 text-[10px] text-secondary ${className}`}>
        {nodeTypes.map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={`overlay-menu rounded-lg p-3 ${className}`}>
      <div className="mb-3">
        <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Node Types</h4>
        <div className="flex flex-col gap-1.5">
          {nodeTypes.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border border-border" style={{ backgroundColor: color }} />
              <span className="text-xs text-primary">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-3">
        <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Sources</h4>
        <div className="grid grid-cols-2 gap-1.5">
          {sourceTypes.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-secondary">{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Relationships</h4>
        <div className="flex flex-wrap gap-1.5">
          {relationships.map(({ type, label }) => (
            <span key={type} className="text-[10px] text-secondary bg-elevated border border-border px-1.5 py-0.5 rounded">
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
