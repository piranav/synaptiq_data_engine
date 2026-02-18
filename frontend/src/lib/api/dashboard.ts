const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export interface DashboardStats {
    concepts_count: number;
    sources_count: number;
    chunks_count: number;
    definitions_count: number;
    relationships_count: number;
    graph_uri: string | null;
    growth_percent?: number | null;
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

interface SourcesApiResponse {
    sources: Array<{
        id: string;
        source_type?: string;
        source_title?: string;
        source_url?: string;
        ingested_at?: string;
    }>;
}

interface JobsApiResponse {
    jobs: Array<{
        id: string;
        status: string;
        source_type?: string;
        source_url?: string;
        created_at: string;
    }>;
}

interface DashboardApiResponse {
    stats: DashboardStats;
    recent_sources?: Array<{
        id: string;
        type?: string;
        title?: string;
        url?: string;
        time?: string;
    }>;
    active_jobs?: JobsApiResponse["jobs"];
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

            const sourcesData = await sourcesRes.json() as SourcesApiResponse;
            const jobsData = await jobsRes.json() as JobsApiResponse;

            // Map sources to activity items
            const sourceItems: ActivityItem[] = sourcesData.sources.map((source) => ({
                id: source.id,
                type: source.source_type || "unknown",
                title: source.source_title || "Untitled",
                source: this.formatSourceUrl(source.source_url || ""),
                time: source.ingested_at || new Date().toISOString(),
                status: "completed",
            }));

            // Collect normalized source URLs so we can deduplicate against jobs
            const sourceUrls = new Set(
                sourcesData.sources
                    .map((source) => source.source_url || "")
                    .map((sourceUrl) => this.normalizeUrl(sourceUrl))
            );

            // Filter out stale jobs (stuck in processing for over 1 hour)
            const ONE_HOUR_MS = 60 * 60 * 1000;
            const now = Date.now();

            // Map jobs to activity items, excluding completed, already-ingested, or stale jobs
            const jobItems: ActivityItem[] = jobsData.jobs
                .filter((job) => {
                    if (job.status === "completed") return false;
                    if (sourceUrls.has(this.normalizeUrl(job.source_url || ""))) return false;
                    // Exclude stale processing jobs (stuck for over 1 hour)
                    if (job.status === "processing") {
                        const jobAge = now - new Date(job.created_at).getTime();
                        if (jobAge > ONE_HOUR_MS) return false;
                    }
                    return true;
                })
                .map((job) => ({
                    id: job.id,
                    type: job.source_type || "unknown",
                    title: job.source_url || "Untitled",
                    source: "Ingesting...",
                    time: job.created_at,
                    status: job.status as "processing" | "failed",
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
        jobs: Job[];
        recentSources: ActivityItem[];
    }> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/user/dashboard`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) return { stats: null, activity: [], jobs: [], recentSources: [] };
            if (!res.ok) throw new Error("Failed to fetch dashboard");

            const data = await res.json() as DashboardApiResponse;

            // Map sources to activity items
            const sourceItems: ActivityItem[] = (data.recent_sources || []).map((source) => ({
                id: source.id,
                type: source.type || "unknown",
                title: source.title || "Untitled",
                source: this.formatSourceUrl(source.url || ""),
                time: source.time || new Date().toISOString(),
                status: "completed" as const,
            }));

            // Collect normalized source URLs so we can deduplicate against jobs
            const sourceUrls = new Set(
                (data.recent_sources || [])
                    .map((source) => source.url || "")
                    .map((sourceUrl) => this.normalizeUrl(sourceUrl))
            );

            // Filter out stale jobs (stuck in processing for over 1 hour)
            const ONE_HOUR_MS = 60 * 60 * 1000;
            const now = Date.now();

            // Map jobs to activity items, excluding completed, already-ingested, or stale jobs
            const jobItems: ActivityItem[] = (data.active_jobs || [])
                .filter((job) => {
                    if (job.status === "completed") return false;
                    if (sourceUrls.has(this.normalizeUrl(job.source_url || ""))) return false;
                    // Exclude stale processing jobs (stuck for over 1 hour)
                    if (job.status === "processing") {
                        const jobAge = now - new Date(job.created_at).getTime();
                        if (jobAge > ONE_HOUR_MS) return false;
                    }
                    return true;
                })
                .map((job) => ({
                    id: job.id,
                    type: job.source_type || "unknown",
                    title: job.source_url || "Untitled",
                    source: "Ingesting...",
                    time: job.created_at,
                    status: job.status as "processing" | "failed",
                }));

            // Merge and sort
            const activity = [...jobItems, ...sourceItems]
                .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
                .slice(0, 5);

            const jobs: Job[] = (data.active_jobs || []).map((job) => ({
                id: String(job.id),
                status: String(job.status),
                source_type: String(job.source_type || "unknown"),
                source_url: String(job.source_url || ""),
                created_at: String(job.created_at),
            }));

            return {
                stats: data.stats,
                activity,
                jobs,
                recentSources: sourceItems,
            };
        } catch (error) {
            console.error("getDashboard failed", error);
            return { stats: null, activity: [], jobs: [], recentSources: [] };
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
        } catch {
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
