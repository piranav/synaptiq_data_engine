"use client";

import { useState } from "react";
import { Filter, ChevronDown, ChevronUp } from "lucide-react";
import type { GraphFilters } from "@/lib/api/graph";

const ALL_REL_TYPES = [
  { id: "isA", label: "Is A" },
  { id: "partOf", label: "Part Of" },
  { id: "prerequisiteFor", label: "Prerequisite For" },
  { id: "usedIn", label: "Used In" },
  { id: "oppositeOf", label: "Opposite Of" },
  { id: "relatedTo", label: "Related To" },
];

interface GraphFiltersPanelProps {
  filters: GraphFilters;
  onFiltersChange: (filters: GraphFilters) => void;
}

export function GraphFiltersPanel({ filters, onFiltersChange }: GraphFiltersPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const activeCount =
    (filters.relTypes?.length || 0) +
    (filters.sourceFilter ? 1 : 0) +
    (filters.minImportance ? 1 : 0);

  const toggleRelType = (relType: string) => {
    const current = filters.relTypes || [];
    const next = current.includes(relType)
      ? current.filter((t) => t !== relType)
      : [...current, relType];
    onFiltersChange({ ...filters, relTypes: next.length > 0 ? next : undefined });
  };

  return (
    <div className="absolute bottom-6 left-6 z-20">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 border border-border rounded-xl px-4 py-2.5 text-sm text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-colors shadow-card bg-surface"
      >
        <Filter className="w-4 h-4" />
        <span>Filters</span>
        {activeCount > 0 && (
          <span className="bg-[var(--accent-soft)] border border-accent/35 text-[var(--accent)] text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            {activeCount}
          </span>
        )}
        {expanded ? <ChevronDown className="w-3.5 h-3.5 text-secondary" /> : <ChevronUp className="w-3.5 h-3.5 text-secondary" />}
      </button>

      {expanded && (
        <div className="mt-2 rounded-xl p-4 shadow-elevated w-64 space-y-4 overlay-menu">
          <div>
            <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Relationship Types</h4>
            <div className="flex flex-wrap gap-1.5">
              {ALL_REL_TYPES.map(({ id, label }) => {
                const active = !filters.relTypes || filters.relTypes.includes(id);
                return (
                  <button
                    key={id}
                    onClick={() => toggleRelType(id)}
                    className={`text-[11px] px-2.5 py-1 rounded-lg border transition-colors ${
                      active
                        ? "bg-[var(--accent-soft)] border-accent/35 text-[var(--accent)]"
                        : "bg-elevated border-border text-secondary hover:text-primary"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Source</h4>
            <input
              type="text"
              value={filters.sourceFilter || ""}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  sourceFilter: e.target.value || undefined,
                })
              }
              placeholder="Filter by source title..."
              className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-primary placeholder:text-secondary focus:outline-none focus:border-accent/45"
            />
          </div>

          <div>
            <h4 className="text-[10px] font-semibold text-tertiary uppercase tracking-wider mb-2">Min Importance: {filters.minImportance ?? 0}</h4>
            <input
              type="range"
              min={0}
              max={50}
              step={1}
              value={filters.minImportance ?? 0}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  minImportance: Number(e.target.value) > 0 ? Number(e.target.value) : undefined,
                })
              }
              className="w-full accent-[var(--accent)]"
            />
          </div>

          {activeCount > 0 && (
            <button
              onClick={() => onFiltersChange({})}
              className="w-full text-[11px] text-secondary hover:text-primary transition-colors py-1"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
