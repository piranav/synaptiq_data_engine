"use client";

import { useEffect, useState } from "react";
import { Brain, Database, FileText, ArrowUpRight } from "lucide-react";
import { dashboardService, DashboardStats } from "@/lib/api/dashboard";

const initialStats = [
    { id: "concepts", label: "Concepts", value: "-", trend: "loading...", icon: Brain },
    { id: "sources", label: "Sources", value: "-", trend: "loading...", icon: Database },
    { id: "notes", label: "Definitions", value: "-", trend: "loading...", icon: FileText },
];

export function StatsRow() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const data = await dashboardService.getStats();
                setStats(data);
            } catch (error) {
                console.error("Failed to fetch stats", error);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, []);

    const displayStats = [
        {
            label: "Concepts",
            value: stats?.concepts_count.toLocaleString() || "-",
            trend: "Total nodes",
            icon: Brain
        },
        {
            label: "Sources",
            value: stats?.sources_count.toLocaleString() || "-",
            trend: "Ingested content",
            icon: Database
        },
        {
            label: "Definitions",
            value: stats?.definitions_count.toLocaleString() || "-",
            trend: "Extracted terms",
            icon: FileText
        },
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {displayStats.map((stat) => {
                const Icon = stat.icon;
                return (
                    <div key={stat.label} className="bg-surface border border-border rounded-xl p-5 shadow-card hover:shadow-hover transition-shadow duration-200 cursor-default">
                        <div className="flex items-start justify-between mb-4">
                            <div className="p-2 bg-canvas rounded-lg text-accent">
                                <Icon className="w-5 h-5" />
                            </div>
                            <ArrowUpRight className="w-4 h-4 text-tertiary" />
                        </div>
                        <div>
                            <div className="text-display text-[32px] mb-1">
                                {loading ? (
                                    <span className="animate-pulse bg-current opacity-20 rounded w-16 h-8 inline-block" />
                                ) : stat.value}
                            </div>
                            <div className="text-body-small text-secondary flex items-center justify-between">
                                <span>{stat.label}</span>
                                <span className="text-success text-caption">{stat.trend}</span>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
