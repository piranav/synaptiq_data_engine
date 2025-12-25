import { authService } from "./auth";

const API_BASE_URL = "http://localhost:8000/api/v1";

export interface IngestResponse {
    job_id: string;
    status: string;
    source_type: string | null;
    message: string;
}

export class IngestService {
    async ingestUrl(url: string, asyncMode: boolean = true): Promise<IngestResponse> {
        const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
        if (!tokens.access_token) {
            throw new Error("No access token found");
        }

        const res = await fetch(`${API_BASE_URL}/ingest`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${tokens.access_token}`,
            },
            body: JSON.stringify({
                url,
                async_mode: asyncMode,
            }),
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail?.message || "Ingestion failed");
        }

        return res.json();
    }

    async uploadFile(file: File): Promise<IngestResponse> {
        const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
        if (!tokens.access_token) {
            throw new Error("No access token found");
        }

        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${API_BASE_URL}/ingest/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${tokens.access_token}`,
                // Content-Type is set automatically with FormData
            },
            body: formData,
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail?.message || "File upload failed");
        }

        return res.json();
    }
}

export const ingestService = new IngestService();
