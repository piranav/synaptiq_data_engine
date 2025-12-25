"use client";

import { useAuth } from "@/contexts/AuthContext";
import { dashboardService } from "@/lib/api/dashboard";
import { BrainCircuit, Quote, Library, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

interface StatsData {
    concepts_count: number;
    sources_count: number;
    definitions_count: number;
}

export function StatsRow() {
    const { user } = useAuth();
    const [stats, setStats] = useState<StatsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        if (!user) return;

        const fetchStats = async () => {
            try {
                const data = await dashboardService.getStats();
                if (data) {
                    setStats(data);
                    setError(false);
                } else {
                    // if null (401), effectively error or just empty. 
                    // Let's treat as error or silent fail.
                    console.warn("Stats data is null (likely 401)");
                    setStats(null);
                    // To avoid error state flash if it's just polling, we might not want setError(true)
                    // But for initial load, maybe we do.
                }
            } catch (err) {
                console.error("Failed to fetch stats for StatsRow", err);
                setError(true);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, [user]);

    const items = [
        {
            label: "Total Concepts",
            value: stats?.concepts_count ?? 0,
            icon: BrainCircuit,
            color: "text-accent",
            bg: "bg-indigo-50",
            trend: "+24",
            trendColor: "text-green-600 bg-green-50"
        },
        {
            label: "Definitions",
            value: stats?.definitions_count ?? 0,
            icon: Quote,
            color: "text-rose-500",
            bg: "bg-rose-50",
            trend: null,
            trendColor: null
        },
        {
            label: "Sources",
            value: stats?.sources_count ?? 0,
            icon: Library,
            color: "text-teal-600",
            bg: "bg-teal-50",
            trend: null,
            trendColor: null
        }
    ];

    if (loading) {
        return (
            <div className="grid grid-cols-3 gap-6 mb-10">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="h-32 rounded-2xl bg-surface border border-border animate-pulse" />
                ))}
            </div>
        );
    }

    if (error) {
        return null;
    }

    return (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            {items.map((item, index) => {
                const Icon = item.icon;
                return (
                    <div key={index} className="bg-surface rounded-2xl p-5 border border-border shadow-subtle flex flex-col justify-between h-32 hover:border-gray-300 transition-colors cursor-default">
                        <div className="flex justify-between items-start">
                            <div className={`p-2 rounded-lg ${item.bg} ${item.color}`}>
                                <Icon className="w-[18px] h-[18px]" />
                            </div>
                            {item.trend && (
                                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${item.trendColor}`}>
                                    {item.trend}
                                </span>
                            )}
                        </div>
                        <div>
                            <div className="text-2xl font-semibold tracking-tight text-primary">
                                {item.value.toLocaleString()}
                            </div>
                            <div className="text-xs text-secondary mt-1 font-medium">
                                {item.label}
                            </div>
                        </div>
                    </div>
                );
            })}
        </section>
    );
}
