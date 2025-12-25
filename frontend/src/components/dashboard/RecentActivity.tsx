"use client";

import { useEffect, useState } from "react";
import { PlayCircle, FileText, Globe, Loader2, AlertCircle } from "lucide-react";
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

    const getIcon = (type: string) => {
        if (['youtube', 'video'].includes(type.toLowerCase())) return PlayCircle;
        if (['note'].includes(type.toLowerCase())) return FileText;
        return Globe; // Default to globe for articles, pdfs, etc.
    };

    const getTypeColor = (type: string) => {
        const t = type.toLowerCase();
        if (['youtube', 'video'].includes(t)) return "bg-red-100 text-red-600";
        if (['note'].includes(t)) return "bg-yellow-100 text-yellow-600";
        return "bg-blue-100 text-blue-600";
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
        <div className="bg-surface border border-border rounded-xl shadow-card overflow-hidden">
            <div className="p-4 border-b border-border bg-canvas/50 flex justify-between items-center">
                <h3 className="text-title-3">Recent Activity</h3>
                {loading && <Loader2 className="w-4 h-4 animate-spin text-tertiary" />}
            </div>
            <div>
                {activities.length === 0 && !loading ? (
                    <div className="p-8 text-center text-secondary">
                        <p>No recent activity.</p>
                    </div>
                ) : (
                    activities.map((item, i) => {
                        const Icon = getIcon(item.type);
                        const isProcessing = item.status === "processing";
                        const isFailed = item.status === "failed";

                        return (
                            <div
                                key={item.id}
                                className={clsx(
                                    "flex items-center p-4 hover:bg-canvas transition-colors cursor-pointer group",
                                    i !== activities.length - 1 && "border-b border-border-subtle"
                                )}
                            >
                                <div className={clsx(
                                    "w-10 h-10 rounded-lg flex items-center justify-center shrink-0 mr-4",
                                    isFailed ? "bg-red-50 text-red-500" : getTypeColor(item.type)
                                )}>
                                    {isFailed ? <AlertCircle className="w-5 h-5" /> : (
                                        isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Icon className="w-5 h-5" />
                                    )}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h4 className="text-body font-medium truncate group-hover:text-accent transition-colors">
                                        {item.title || "Untitled"}
                                    </h4>
                                    <p className="text-caption text-secondary mt-0.5">
                                        {item.source} • {formatTime(item.time)}
                                    </p>
                                </div>
                                <div className="text-caption text-tertiary">
                                    {isProcessing ? (
                                        <span className="text-accent">Processing...</span>
                                    ) : isFailed ? (
                                        <span className="text-danger">Failed</span>
                                    ) : (
                                        "Added"
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
            <div className="p-3 bg-canvas/30 border-t border-border text-center">
                <Link href="/library" className="text-callout text-accent hover:underline">
                    View full library
                </Link>
            </div>
        </div>
    );
}
