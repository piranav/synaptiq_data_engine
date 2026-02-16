
const API_BASE_URL = "http://localhost:8000/api/v1";

export interface DashboardStats {
    concepts_count: number;
    sources_count: number;
    chunks_count: number;
    definitions_count: number;
    relationships_count: number;
    graph_uri: string | null;
}

export interface ActivityItem {
    id: string;
    type: string;
    title: string;
    source: string;
    time: string;
    status: "completed" | "processing" | "failed";
}

export interface Job {
    id: string;
    status: string;
    source_type: string;
    source_url: string;
    created_at: string;
}

export class DashboardService {
    private getToken(): string {
        const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
        if (!tokens.access_token) {
            throw new Error("No access token found");
        }
        return tokens.access_token;
    }

    async getStats(): Promise<DashboardStats | null> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/user/stats`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) return null;
            if (!res.ok) throw new Error("Failed to fetch stats");

            return res.json();
        } catch (error) {
            console.error("getStats failed", error);
            return null;
        }
    }

    async getRecentActivity(limit: number = 5): Promise<ActivityItem[]> {
        try {
            const token = this.getToken();

            // 1. Fetch recent sources (completed)
            const sourcesRes = await fetch(`${API_BASE_URL}/sources?limit=${limit}`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (sourcesRes.status === 401) return [];

            // 2. Fetch active/recent jobs (processing/failed)
            const jobsRes = await fetch(`${API_BASE_URL}/jobs?limit=${limit}`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (jobsRes.status === 401) return [];

            if (!sourcesRes.ok || !jobsRes.ok) {
                return [];
            }

            const sourcesData = await sourcesRes.json();
            const jobsData = await jobsRes.json();

            // Map sources to activity items
            const sourceItems: ActivityItem[] = sourcesData.sources.map((s: any) => ({
                id: s.id,
                type: s.source_type,
                title: s.source_title,
                source: this.formatSourceUrl(s.source_url),
                time: s.ingested_at,
                status: "completed",
            }));

            // Collect normalized source URLs so we can deduplicate against jobs
            const sourceUrls = new Set(sourcesData.sources.map((s: any) => this.normalizeUrl(s.source_url)));

            // Filter out stale jobs (stuck in processing for over 1 hour)
            const ONE_HOUR_MS = 60 * 60 * 1000;
            const now = Date.now();

            // Map jobs to activity items, excluding completed, already-ingested, or stale jobs
            const jobItems: ActivityItem[] = jobsData.jobs
                .filter((j: any) => {
                    if (j.status === "completed") return false;
                    if (sourceUrls.has(this.normalizeUrl(j.source_url))) return false;
                    // Exclude stale processing jobs (stuck for over 1 hour)
                    if (j.status === "processing") {
                        const jobAge = now - new Date(j.created_at).getTime();
                        if (jobAge > ONE_HOUR_MS) return false;
                    }
                    return true;
                })
                .map((j: any) => ({
                    id: j.id,
                    type: j.source_type || "unknown",
                    title: j.source_url,
                    source: "Ingesting...",
                    time: j.created_at,
                    status: j.status,
                }));

            // Merge and sort
            const allItems = [...jobItems, ...sourceItems]
                .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
                .slice(0, limit);

            return allItems;
        } catch (error) {
            console.error("getRecentActivity failed", error);
            return [];
        }
    }

    /**
     * Get all dashboard data in a single optimized request.
     * This replaces getStats() + getRecentActivity() with a single API call.
     */
    async getDashboard(): Promise<{
        stats: DashboardStats | null;
        activity: ActivityItem[];
    }> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/user/dashboard`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) return { stats: null, activity: [] };
            if (!res.ok) throw new Error("Failed to fetch dashboard");

            const data = await res.json();

            // Map sources to activity items
            const sourceItems: ActivityItem[] = (data.recent_sources || []).map((s: any) => ({
                id: s.id,
                type: s.type,
                title: s.title,
                source: this.formatSourceUrl(s.url),
                time: s.time,
                status: "completed" as const,
            }));

            // Collect normalized source URLs so we can deduplicate against jobs
            const sourceUrls = new Set((data.recent_sources || []).map((s: any) => this.normalizeUrl(s.url)));

            // Filter out stale jobs (stuck in processing for over 1 hour)
            const ONE_HOUR_MS = 60 * 60 * 1000;
            const now = Date.now();

            // Map jobs to activity items, excluding completed, already-ingested, or stale jobs
            const jobItems: ActivityItem[] = (data.active_jobs || [])
                .filter((j: any) => {
                    if (j.status === "completed") return false;
                    if (sourceUrls.has(this.normalizeUrl(j.source_url))) return false;
                    // Exclude stale processing jobs (stuck for over 1 hour)
                    if (j.status === "processing") {
                        const jobAge = now - new Date(j.created_at).getTime();
                        if (jobAge > ONE_HOUR_MS) return false;
                    }
                    return true;
                })
                .map((j: any) => ({
                    id: j.id,
                    type: j.source_type || "unknown",
                    title: j.source_url,
                    source: "Ingesting...",
                    time: j.created_at,
                    status: j.status as "processing" | "failed",
                }));

            // Merge and sort
            const activity = [...jobItems, ...sourceItems]
                .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
                .slice(0, 5);

            return {
                stats: data.stats,
                activity,
            };
        } catch (error) {
            console.error("getDashboard failed", error);
            return { stats: null, activity: [] };
        }
    }

    async getActiveJobs(): Promise<Job[]> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/jobs?status=processing`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) return [];
            if (!res.ok) return [];

            const data = await res.json();
            return data.jobs;
        } catch (error) {
            // silent fail for polling
            return [];
        }
    }

    private normalizeUrl(url: string): string {
        const ytMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([\w-]+)/i);
        if (ytMatch) return `https://www.youtube.com/watch?v=${ytMatch[1]}`;
        return url;
    }

    private formatSourceUrl(url: string): string {
        try {
            const domain = new URL(url).hostname.replace("www.", "");
            return domain.charAt(0).toUpperCase() + domain.slice(1);
        } catch {
            return "Source";
        }
    }
}

export const dashboardService = new DashboardService();
