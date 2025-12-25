"use client";

import { useEffect, useState } from "react";
import { PlayCircle, FileText, Globe, Loader2, AlertCircle, Youtube, StickyNote, MessageSquare } from "lucide-react";
import clsx from "clsx";
import { dashboardService, ActivityItem } from "@/lib/api/dashboard";
import Link from "next/link";

export function RecentActivity() {
    const [activities, setActivities] = useState<ActivityItem[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchActivity = async () => {
        try {
            const data = await dashboardService.getRecentActivity();
            setActivities(data);
        } catch (error) {
            console.error("Failed to fetch activity", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchActivity();
        const interval = setInterval(fetchActivity, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, []);

    const getSourceIcon = (type: string) => {
        const t = type.toLowerCase();
        if (['youtube', 'video'].includes(t)) return { icon: Youtube, bg: 'bg-teal-50', color: 'text-teal-600' };
        if (['note', 'file'].includes(t)) return { icon: StickyNote, bg: 'bg-indigo-50', color: 'text-indigo-600' };
        if (['chat', 'conversation'].includes(t)) return { icon: MessageSquare, bg: 'bg-gray-50', color: 'text-gray-600' };
        return { icon: Globe, bg: 'bg-blue-50', color: 'text-blue-600' };
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        const now = new Date();
        const diff = (now.getTime() - date.getTime()) / 1000; // seconds

        if (diff < 60) return "Just now";
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return date.toLocaleDateString();
    };

    return (
        <section className="flex flex-col h-full">
            <div className="flex items-center justify-between mb-4 px-1">
                <h2 className="text-sm font-semibold text-primary">Recent Activity</h2>
                <Link href="/library" className="text-xs text-secondary hover:text-accent transition-colors">View all</Link>
            </div>

            <div className="flex-1 flex flex-col gap-3">
                {loading && activities.length === 0 && (
                    <div className="flex justify-center items-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-tertiary" />
                    </div>
                )}

                {!loading && activities.length === 0 && (
                    <div className="text-center py-8 text-secondary text-sm">
                        No recent activity
                    </div>
                )}

                {activities.map((activity) => {
                    const iconData = getSourceIcon(activity.type || 'unknown');
                    const Icon = iconData.icon;
                    const timeDisplay = formatTime(activity.time || new Date().toISOString());

                    return (
                        <div key={activity.id} className="group flex items-start p-3 rounded-xl bg-surface border border-border hover:border-gray-300 transition-all cursor-pointer shadow-sm">
                            <div className={clsx(
                                "mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                                activity.status === "failed" ? "bg-red-50 text-red-500" : `${iconData.bg} ${iconData.color}`
                            )}>
                                {activity.status === "failed" ? <AlertCircle className="w-3.5 h-3.5" /> : (
                                    activity.status === "processing" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />
                                )}
                            </div>
                            <div className="ml-3 flex-1 min-w-0">
                                <p className="text-sm font-medium text-primary truncate">{activity.title || "Untitled"}</p>
                                <p className="text-xs text-secondary mt-0.5 truncate">{activity.source || "Unknown source"}</p>
                            </div>
                            <div className="flex flex-col items-end gap-1 mt-1">
                                <span className="text-[10px] text-gray-400 whitespace-nowrap">{timeDisplay}</span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}
