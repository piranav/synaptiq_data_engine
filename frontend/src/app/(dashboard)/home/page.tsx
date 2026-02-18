"use client";

import { useAuth } from "@/contexts/AuthContext";
import { QuickCapture } from "@/components/dashboard/QuickCapture";
import { StatsRow } from "@/components/dashboard/StatsRow";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { dashboardService } from "@/lib/api/dashboard";
import { IngestionHealth } from "@/components/dashboard/IngestionHealth";
import { SourceMix } from "@/components/dashboard/SourceMix";
import { GraphSpotlight } from "@/components/dashboard/GraphSpotlight";
import { Loader2, CalendarDays, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";

export default function HomePage() {
    const { user } = useAuth();
    const firstName = user?.name?.split(" ")[0] || user?.email?.split("@")[0] || "there";
    const [stats, setStats] = useState<Awaited<ReturnType<typeof dashboardService.getStats>>>(null);
    const [activity, setActivity] = useState<Awaited<ReturnType<typeof dashboardService.getRecentActivity>>>([]);
    const [jobs, setJobs] = useState<Awaited<ReturnType<typeof dashboardService.getActiveJobs>>>([]);
    const [recentSources, setRecentSources] = useState<Awaited<ReturnType<typeof dashboardService.getRecentActivity>>>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!user) return;

        const loadDashboard = async () => {
            try {
                setLoading(true);
                const dashboard = await dashboardService.getDashboard();

                if (!dashboard.stats && dashboard.activity.length === 0) {
                    // Resilience fallback for older API payloads
                    const [fallbackStats, fallbackActivity, fallbackJobs] = await Promise.all([
                        dashboardService.getStats(),
                        dashboardService.getRecentActivity(),
                        dashboardService.getActiveJobs(),
                    ]);
                    setStats(fallbackStats);
                    setActivity(fallbackActivity);
                    setRecentSources(fallbackActivity.filter((item) => item.status === "completed"));
                    setJobs(fallbackJobs);
                    return;
                }

                setStats(dashboard.stats);
                setActivity(dashboard.activity);
                setJobs(dashboard.jobs);
                setRecentSources(dashboard.recentSources.filter((item) => item.status === "completed"));
            } catch (err) {
                console.error("Failed to load dashboard", err);
            } finally {
                setLoading(false);
            }
        };

        loadDashboard();
    }, [user]);

    // Generate greeting based on time of day
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 17) return "Good afternoon";
        return "Good evening";
    };

    // Generate subtitle based on growth
    const getSubtitle = () => {
        const growthPercent = stats?.growth_percent ?? null;
        if (growthPercent !== null && growthPercent > 0) {
            return `Your graph has grown by ${growthPercent.toFixed(1)}% this week. Ready to capture?`;
        } else if (growthPercent === 0) {
            return "Your graph is stable. Ready to add more knowledge?";
        }
        return "Ready to capture some knowledge?";
    };

    const dateBadge = new Date();
    const dayNumber = dateBadge.getDate();
    const dayLabel = dateBadge.toLocaleDateString(undefined, { weekday: "short" });
    const monthLabel = dateBadge.toLocaleDateString(undefined, { month: "long" });

    return (
        <div className="w-full max-w-[1420px] mx-auto py-6 md:py-8 flex flex-col gap-5 md:gap-6 animation-fade-in-up">
            <section className="dashboard-card p-5 md:p-6">
                <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-center">
                    <div className="xl:col-span-5 flex flex-wrap items-center gap-4 md:gap-5">
                        <div className="w-20 h-20 rounded-full border border-border bg-elevated flex items-center justify-center text-primary">
                            <div className="text-center leading-none">
                                <p className="text-[30px] font-semibold tracking-tight">{dayNumber}</p>
                            </div>
                        </div>
                        <div>
                            <p className="text-[22px] font-semibold tracking-tight text-primary">{dayLabel}, {monthLabel}</p>
                            <p className="text-sm text-secondary mt-1">Knowledge workspace snapshot</p>
                        </div>
                        <button className="md:ml-auto dashboard-pill px-4 h-10 text-sm font-medium text-white bg-accent border-accent hover:bg-[var(--accent-hover)] transition-colors">
                            Show tasks
                            <ArrowRight className="w-4 h-4 ml-2" />
                        </button>
                    </div>

                    <div className="xl:col-span-7 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                        <div>
                            <h1 className="text-[35px] leading-[1.05] font-semibold tracking-tight text-primary">{getGreeting()}, {firstName}</h1>
                            <p className="text-secondary font-normal text-base mt-1">{getSubtitle()}</p>
                        </div>
                        <div className="dashboard-pill h-11 px-4 text-sm text-secondary gap-2 self-start md:self-auto">
                            <CalendarDays className="w-4 h-4" />
                            {loading ? (
                                <>
                                    <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                                    <span>Syncing dashboard</span>
                                </>
                            ) : (
                                <>
                                    <span className="inline-flex w-2 h-2 rounded-full bg-success" />
                                    <span>Dashboard synced</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </section>

            <QuickCapture />

            <StatsRow stats={stats} loading={loading} />

            <section className="grid grid-cols-1 xl:grid-cols-12 gap-5 md:gap-6">
                <div className="xl:col-span-8 space-y-5 md:space-y-6">
                    <GraphSpotlight />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 md:gap-6">
                        <SourceMix sources={recentSources} />
                        <IngestionHealth jobs={jobs} />
                    </div>
                </div>
                <div className="xl:col-span-4 h-full min-h-[580px]">
                    <RecentActivity activities={activity} loading={loading} />
                </div>
            </section>
        </div>
    );
}
