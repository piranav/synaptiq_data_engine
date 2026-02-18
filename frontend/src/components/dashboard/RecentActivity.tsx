"use client";

import { useEffect, useState } from "react";
import { Globe, Loader2, AlertCircle, Youtube, StickyNote, MessageSquare, RefreshCcw } from "lucide-react";
import clsx from "clsx";
import { dashboardService, ActivityItem } from "@/lib/api/dashboard";
import Link from "next/link";
import { IconFrame } from "@/components/ui/IconFrame";

interface RecentActivityProps {
    activities?: ActivityItem[];
    loading?: boolean;
    onRefresh?: () => void;
}

export function RecentActivity({ activities: incomingActivities, loading: incomingLoading, onRefresh }: RecentActivityProps) {
    const [activities, setActivities] = useState<ActivityItem[]>(incomingActivities || []);
    const [loading, setLoading] = useState(incomingLoading ?? !incomingActivities);

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
        if (incomingActivities) {
            setActivities(incomingActivities);
            setLoading(incomingLoading ?? false);
            return;
        }

        fetchActivity();
        const interval = setInterval(fetchActivity, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, [incomingActivities, incomingLoading]);

    const getSourceIconTone = (type: string) => {
        const t = type.toLowerCase();
        if (["youtube", "video"].includes(t)) return { icon: Youtube, tone: "source" as const };
        if (["note", "file"].includes(t)) return { icon: StickyNote, tone: "relation" as const };
        if (["chat", "conversation"].includes(t)) return { icon: MessageSquare, tone: "neutral" as const };
        return { icon: Globe, tone: "concept" as const };
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
        <section className="dashboard-card flex flex-col h-full rounded-[26px] p-5">
            <div className="flex items-center justify-between mb-5">
                <h2 className="text-sm font-semibold text-primary">Recent Activity</h2>
                <div className="flex items-center gap-2">
                    {onRefresh && (
                        <button
                            onClick={onRefresh}
                            className="h-8 w-8 rounded-full border border-border text-secondary hover:text-primary hover:bg-[var(--hover-bg)] inline-flex items-center justify-center"
                            title="Refresh dashboard"
                        >
                            <RefreshCcw className="w-3.5 h-3.5" />
                        </button>
                    )}
                    <Link href="/library" className="dashboard-pill h-8 px-3 text-xs text-secondary hover:text-primary transition-colors">
                        View all
                    </Link>
                </div>
            </div>

            <div className="flex-1 flex flex-col gap-2.5">
                {loading && activities.length === 0 && (
                    <div className="flex justify-center items-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-secondary" />
                    </div>
                )}

                {!loading && activities.length === 0 && (
                    <div className="text-center py-8 text-secondary text-sm">
                        No recent activity
                    </div>
                )}

                {activities.map((activity) => {
                    const iconData = getSourceIconTone(activity.type || "unknown");
                    const Icon = iconData.icon;
                    const timeDisplay = formatTime(activity.time || new Date().toISOString());

                    return (
                        <div key={activity.id} className="group flex items-start p-3 rounded-[16px] bg-elevated border border-border hover:shadow-card transition-all">
                            <div className={clsx("mt-0.5 flex-shrink-0", activity.status === "processing" && "animate-pulse")}>
                                {activity.status === "failed" ? (
                                    <IconFrame icon={AlertCircle} tone="danger" size="sm" />
                                ) : activity.status === "processing" ? (
                                    <IconFrame icon={Loader2} tone="accent" size="sm" iconClassName="animate-spin" />
                                ) : (
                                    <IconFrame icon={Icon} tone={iconData.tone} size="sm" />
                                )}
                            </div>
                            <div className="ml-3 flex-1 min-w-0">
                                <p className="text-sm font-medium text-primary truncate">{activity.title || "Untitled"}</p>
                                <p className="text-xs text-secondary mt-0.5 truncate">{activity.source || "Unknown source"}</p>
                            </div>
                            <div className="flex flex-col items-end gap-1 mt-1">
                                <span className="text-[10px] text-secondary whitespace-nowrap">{timeDisplay}</span>
                                <span className={clsx(
                                    "text-[10px] px-1.5 py-0.5 rounded border",
                                    activity.status === "completed" && "text-success border-success/30 bg-success/10",
                                    activity.status === "processing" && "text-accent border-accent/30 bg-accent/10",
                                    activity.status === "failed" && "text-danger border-danger/30 bg-danger/10"
                                )}>
                                    {activity.status}
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}
