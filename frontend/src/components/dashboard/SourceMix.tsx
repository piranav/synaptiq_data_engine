"use client";

import { PieChart } from "lucide-react";
import type { ActivityItem } from "@/lib/api/dashboard";
import { IconFrame } from "@/components/ui/IconFrame";

interface SourceMixProps {
    sources: ActivityItem[];
}

const sourceLabelMap: Record<string, string> = {
    youtube: "YouTube",
    video: "Video",
    web_article: "Web",
    web: "Web",
    note: "Notes",
    file: "Files",
    pdf: "PDF",
    unknown: "Other",
};

export function SourceMix({ sources }: SourceMixProps) {
    const counts = new Map<string, number>();
    for (const source of sources) {
        const key = (source.type || "unknown").toLowerCase();
        counts.set(key, (counts.get(key) || 0) + 1);
    }

    const total = Array.from(counts.values()).reduce((sum, value) => sum + value, 0);
    const rows = Array.from(counts.entries())
        .map(([type, count]) => ({
            type,
            label: sourceLabelMap[type] || type,
            count,
            percentage: total === 0 ? 0 : Math.round((count / total) * 100),
        }))
        .sort((a, b) => b.count - a.count);

    return (
        <section className="dashboard-card rounded-[24px] p-5 h-full">
            <div className="flex items-center gap-2.5 mb-4">
                <IconFrame icon={PieChart} tone="relation" />
                <h3 className="text-sm font-semibold text-primary">Source Mix</h3>
            </div>

            {rows.length === 0 ? (
                <p className="text-xs text-secondary">Ingest a source to see distribution.</p>
            ) : (
                <div className="space-y-2.5">
                    {rows.map((row) => (
                        <div key={row.type} className="rounded-[16px] border border-border-subtle bg-elevated p-3">
                            <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-primary font-medium">{row.label}</span>
                                <span className="text-secondary">{row.count} · {row.percentage}%</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-surface overflow-hidden">
                                <div
                                    className="h-full rounded-full bg-accent"
                                    style={{ width: `${Math.max(8, row.percentage)}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}
