/**
 * Library API service for managing sources/library items.
 * Wraps the /sources endpoints with library-specific types.
 */

const API_BASE_URL = "http://localhost:8000/api/v1";

// Types
export type LibraryItemType = "video" | "article" | "note" | "file" | "youtube" | "web";

export interface LibraryItem {
    id: string;
    type: LibraryItemType;
    title: string;
    url: string;
    conceptCount: number;
    ingestedAt: string;
    thumbnail?: string;
}

export interface LibraryStats {
    all: number;
    videos: number;
    articles: number;
    notes: number;
    files: number;
}

export interface LibraryFilter {
    type?: LibraryItemType | "all";
    sort?: "recent" | "oldest" | "alphabetical";
    search?: string;
    limit?: number;
    offset?: number;
}

export interface LibraryItemDetail extends LibraryItem {
    contentPreview: string;
    segmentCount: number;
    metadata: Record<string, unknown>;
}

class LibraryService {
    private getToken(): string {
        const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
        if (!tokens.access_token) {
            throw new Error("No access token found");
        }
        return tokens.access_token;
    }

    /**
     * Fetch library items with optional filtering
     */
    async getLibraryItems(filter: LibraryFilter = {}): Promise<LibraryItem[]> {
        try {
            const token = this.getToken();
            const params = new URLSearchParams();

            if (filter.type && filter.type !== "all") {
                // Map frontend types to backend source_type
                // Backend uses: youtube, web_article, note, pdf, docx
                const typeMap: Record<string, string> = {
                    video: "youtube",
                    videos: "youtube",
                    youtube: "youtube",
                    article: "web_article",
                    articles: "web_article",
                    web: "web_article",
                    web_article: "web_article",
                    note: "note",
                    notes: "note",
                    file: "pdf",  // TODO: Support filtering multiple file types
                    files: "pdf",
                };
                params.append("source_type", typeMap[filter.type] || filter.type);
            }

            params.append("limit", String(filter.limit || 100));
            params.append("offset", String(filter.offset || 0));

            const res = await fetch(`${API_BASE_URL}/sources?${params.toString()}`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401) return [];
            if (!res.ok) throw new Error("Failed to fetch library items");

            const data = await res.json();

            // Map to LibraryItem format
            let items: LibraryItem[] = data.sources.map((s: any) => ({
                id: s.id,
                type: this.mapSourceType(s.source_type),
                title: s.source_title || "Untitled",
                url: s.source_url,
                conceptCount: 0, // Will be populated from detail if needed
                ingestedAt: s.ingested_at,
            }));

            // Apply client-side sorting
            if (filter.sort === "oldest") {
                items.sort((a, b) => new Date(a.ingestedAt).getTime() - new Date(b.ingestedAt).getTime());
            } else if (filter.sort === "alphabetical") {
                items.sort((a, b) => a.title.localeCompare(b.title));
            } else {
                // Default: recent first
                items.sort((a, b) => new Date(b.ingestedAt).getTime() - new Date(a.ingestedAt).getTime());
            }

            // Apply client-side search
            if (filter.search) {
                const searchLower = filter.search.toLowerCase();
                items = items.filter(
                    (item) =>
                        item.title.toLowerCase().includes(searchLower) ||
                        item.url.toLowerCase().includes(searchLower)
                );
            }

            return items;
        } catch (error) {
            console.error("getLibraryItems failed", error);
            return [];
        }
    }

    /**
     * Get statistics for tab badges by computing from all items
     * Note: The /sources/stats endpoint has a route conflict with /{source_id}
     * so we compute stats client-side from the full item list
     */
    async getLibraryStats(): Promise<LibraryStats> {
        try {
            // Fetch all items to compute stats
            const items = await this.getLibraryItems({ type: "all", limit: 500 });

            const stats: LibraryStats = {
                all: items.length,
                videos: 0,
                articles: 0,
                notes: 0,
                files: 0,
            };

            for (const item of items) {
                // mapSourceType already normalizes types, so we just need to check normalized types
                if (item.type === "video" || item.type === "youtube") {
                    stats.videos++;
                } else if (item.type === "article" || item.type === "web") {
                    stats.articles++;
                } else if (item.type === "note") {
                    stats.notes++;
                } else if (item.type === "file") {
                    stats.files++;
                }
            }

            return stats;
        } catch (error) {
            console.error("getLibraryStats failed", error);
            return { all: 0, videos: 0, articles: 0, notes: 0, files: 0 };
        }
    }

    /**
     * Get detailed information about a library item
     */
    async getItemDetail(id: string): Promise<LibraryItemDetail | null> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/sources/${id}`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 401 || res.status === 404) return null;
            if (!res.ok) throw new Error("Failed to fetch item detail");

            const data = await res.json();

            return {
                id: data.id,
                type: this.mapSourceType(data.source_type),
                title: data.source_title || "Untitled",
                url: data.source_url,
                conceptCount: 0,
                ingestedAt: data.ingested_at,
                contentPreview: data.raw_content_preview || "",
                segmentCount: data.segment_count || 0,
                metadata: data.source_metadata || {},
            };
        } catch (error) {
            console.error("getItemDetail failed", error);
            return null;
        }
    }

    /**
     * Delete a library item
     */
    async deleteItem(id: string): Promise<boolean> {
        try {
            const token = this.getToken();
            const res = await fetch(`${API_BASE_URL}/sources/${id}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 204 || res.ok) return true;
            return false;
        } catch (error) {
            console.error("deleteItem failed", error);
            return false;
        }
    }

    /**
     * Map backend source_type to frontend LibraryItemType
     */
    private mapSourceType(sourceType: string): LibraryItemType {
        const typeMap: Record<string, LibraryItemType> = {
            youtube: "video",
            web: "article",
            web_article: "article",  // Backend uses web_article
            note: "note",
            file: "file",
            pdf: "file",    // PDF files
            docx: "file",   // DOCX files
        };
        return typeMap[sourceType?.toLowerCase()] || "article";
    }
}

export const libraryService = new LibraryService();
