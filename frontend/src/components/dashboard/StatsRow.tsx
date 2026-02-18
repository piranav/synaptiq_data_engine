"use client";

import { BrainCircuit, Link2, Library, TrendingUp } from "lucide-react";
import type { DashboardStats } from "@/lib/api/dashboard";
import clsx from "clsx";
import { IconFrame } from "@/components/ui/IconFrame";

interface StatsRowProps {
    stats?: DashboardStats | null;
    loading?: boolean;
}

export function StatsRow({ stats, loading = false }: StatsRowProps) {
    const growth = stats?.growth_percent ?? null;
    const items = [
        {
            label: "Concepts",
            value: stats?.concepts_count ?? 0,
            icon: BrainCircuit,
            tone: "concept" as const,
            caption: "Total indexed concepts",
        },
        {
            label: "Connections",
            value: stats?.relationships_count ?? 0,
            icon: Link2,
            tone: "relation" as const,
            caption: "Graph relationships",
        },
        {
            label: "Sources",
            value: stats?.sources_count ?? 0,
            icon: Library,
            tone: "source" as const,
            caption: "Ingested sources",
        },
        {
            label: "Weekly Growth",
            value: growth === null ? "N/A" : `${growth > 0 ? "+" : ""}${growth.toFixed(1)}%`,
            icon: TrendingUp,
            tone: growth !== null && growth < 0 ? "danger" as const : "accent" as const,
            caption: growth === null ? "Need 7 days of history" : "Concept growth vs last week",
        },
    ];

    if (loading) {
        return (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 md:gap-5">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-36 rounded-[24px] bg-surface border border-border animate-pulse" />
                ))}
            </div>
        );
    }

    return (
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 md:gap-5">
            {items.map((item, index) => {
                return (
                    <div key={index} className="dashboard-card rounded-[24px] p-5 flex flex-col justify-between min-h-[146px] hover:shadow-hover transition-all">
                        <div className="flex justify-between items-start mb-5">
                            <IconFrame icon={item.icon} tone={item.tone} size="sm" />
                            <span className="text-[10px] uppercase tracking-[0.14em] text-tertiary font-semibold">Live</span>
                        </div>
                        <div>
                            <div className={clsx(
                                "text-[32px] leading-[1] font-semibold tracking-tight text-primary",
                                item.label === "Weekly Growth" && growth !== null && growth > 0 && "text-accent",
                                item.label === "Weekly Growth" && growth !== null && growth < 0 && "text-danger"
                            )}>
                                {typeof item.value === "number" ? item.value.toLocaleString() : item.value}
                            </div>
                            <div className="text-[11px] text-secondary mt-2 font-semibold uppercase tracking-[0.14em]">
                                {item.label}
                            </div>
                            <p className="text-xs text-secondary mt-1">{item.caption}</p>
                        </div>
                    </div>
                );
            })}
        </section>
    );
}
