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

            // Handle 204 No Content (common for DELETE requests)
            if (response.status === 204 || response.headers.get("content-length") === "0") {
                if (!response.ok) {
                    throw new Error(`Request failed with status ${response.status}`);
                }
                return { data: null, status: response.status, ok: response.ok };
            }

            // For DELETE requests, treat 404 as success (idempotent - already deleted)
            if (options.method === "DELETE" && response.status === 404) {
                return { data: null, status: 204, ok: true };
            }

            // Try to parse JSON, handle empty body gracefully
            let data = null;
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const text = await response.text();
                if (text) {
                    data = JSON.parse(text);
                }
            }

            // If the API returns a structured error, throw it
            if (!response.ok) {
                // Extract error message from various possible error formats
                let errorMessage = `Request failed with status ${response.status}`;

                if (data) {
                    // Check common error message properties
                    const msg = data.message || data.detail || data.error;
                    if (typeof msg === 'string') {
                        errorMessage = msg;
                    } else if (msg && typeof msg === 'object') {
                        // Handle nested error objects
                        errorMessage = JSON.stringify(msg);
                    } else if (typeof data === 'string') {
                        errorMessage = data;
                    }
                }

                throw new Error(errorMessage);
            }

            return { data, status: response.status, ok: response.ok };
        } catch (error) {
            const message = error instanceof Error ? error.message : "";
            const isExpectedAuthError = /authentication required|token/i.test(message);
            if (!isExpectedAuthError) {
                console.error(`API Request failed: ${endpoint}`, error);
            }
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

    patch<T>(endpoint: string, data?: any, options?: ApiOptions) {
        return this.request<T>(endpoint, {
            ...options,
            method: "PATCH",
            body: JSON.stringify(data)
        });
    }

    delete<T>(endpoint: string, options?: ApiOptions) {
        return this.request<T>(endpoint, { ...options, method: "DELETE" });
    }
}

export const api = new ApiClient();
