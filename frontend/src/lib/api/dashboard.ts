
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

    async getStats(): Promise<DashboardStats> {
        const token = this.getToken();
        const res = await fetch(`${API_BASE_URL}/user/stats`, {
            headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
            const text = await res.text();
            console.error(`getStats failed: ${res.status} ${res.statusText}`, text);
            throw new Error(`Failed to fetch stats: ${res.status} ${res.statusText}`);
        }

        return res.json();
    }

    async getRecentActivity(limit: number = 5): Promise<ActivityItem[]> {
        const token = this.getToken();

        // 1. Fetch recent sources (completed)
        const sourcesRes = await fetch(`${API_BASE_URL}/sources?limit=${limit}`, {
            headers: { Authorization: `Bearer ${token}` },
        });

        // 2. Fetch active/recent jobs (processing/failed)
        const jobsRes = await fetch(`${API_BASE_URL}/jobs?limit=${limit}`, {
            headers: { Authorization: `Bearer ${token}` },
        });

        if (!sourcesRes.ok) {
            const text = await sourcesRes.text();
            console.error(`fetch sources failed: ${sourcesRes.status} ${sourcesRes.statusText}`, text);
            throw new Error("Failed to fetch activity");
        }

        if (!jobsRes.ok) {
            const text = await jobsRes.text();
            console.error(`fetch jobs failed: ${jobsRes.status} ${jobsRes.statusText}`, text);
            throw new Error("Failed to fetch activity");
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

        // Map jobs to activity items (only if not already in sources, simplified logic for now)
        // We prioritize jobs that are NOT completed, as completed ones should be in sources
        const jobItems: ActivityItem[] = jobsData.jobs
            .filter((j: any) => j.status !== "completed")
            .map((j: any) => ({
                id: j.id,
                type: j.source_type || "unknown",
                title: j.source_url, // We don't have title for jobs yet
                source: "Ingesting...",
                time: j.created_at,
                status: j.status,
            }));

        // Merge and sort
        const allItems = [...jobItems, ...sourceItems]
            .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
            .slice(0, limit);

        return allItems;
    }

    async getActiveJobs(): Promise<Job[]> {
        const token = this.getToken();
        const res = await fetch(`${API_BASE_URL}/jobs?status=processing`, {
            headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
            console.error(`getActiveJobs failed: ${res.status} ${res.statusText}`);
            return [];
        }
        const data = await res.json();
        return data.jobs;
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
