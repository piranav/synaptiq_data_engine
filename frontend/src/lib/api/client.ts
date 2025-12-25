const API_BASE_URL = "http://localhost:8000/api/v1";

interface ApiOptions extends RequestInit {
    headers?: Record<string, string>;
}

class ApiClient {
    private getToken(): string | null {
        if (typeof window === "undefined") return null;
        try {
            const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
            return tokens.access_token || null;
        } catch {
            return null;
        }
    }

    private async request<T>(endpoint: string, options: ApiOptions = {}): Promise<any> {
        const token = this.getToken();
        const headers: Record<string, string> = {
            "Content-Type": "application/json",
            ...options.headers,
        };

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const config: RequestInit = {
            ...options,
            headers,
        };

        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

            // Handle 401 Unauthorized globally if needed (e.g. redirect to login)
            if (response.status === 401) {
                // optional: event emit or redirect
            }

            const data = await response.json();

            // If the API returns a structured error, throw it?
            if (!response.ok) {
                throw new Error(data.message || data.detail || `Request failed with status ${response.status}`);
            }

            return { data, status: response.status, ok: response.ok };
        } catch (error) {
            console.error(`API Request failed: ${endpoint}`, error);
            throw error;
        }
    }

    get<T>(endpoint: string, options?: ApiOptions) {
        return this.request<T>(endpoint, { ...options, method: "GET" });
    }

    post<T>(endpoint: string, data?: any, options?: ApiOptions) {
        return this.request<T>(endpoint, {
            ...options,
            method: "POST",
            body: JSON.stringify(data)
        });
    }

    put<T>(endpoint: string, data?: any, options?: ApiOptions) {
        return this.request<T>(endpoint, {
            ...options,
            method: "PUT",
            body: JSON.stringify(data)
        });
    }

    delete<T>(endpoint: string, options?: ApiOptions) {
        return this.request<T>(endpoint, { ...options, method: "DELETE" });
    }
}

export const api = new ApiClient();
