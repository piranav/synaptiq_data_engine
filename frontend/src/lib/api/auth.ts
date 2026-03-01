const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
const API_ORIGIN = new URL(API_BASE_URL).origin;
export const AUTH_STATE_CHANGED_EVENT = "synaptiq-auth-changed";

// Types derived from backend spec
export interface User {
    id: string;
    email: string;
    name: string | null;
    avatar_url: string | null;
    graph_uri: string | null;
    is_verified: boolean;
    created_at: string;
}

export interface Tokens {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export interface AuthResponse {
    user: User;
    tokens: Tokens;
}

export interface AuthError {
    message: string;
    code: string;
}

export type OAuthProvider = "google" | "github";
export type OAuthMode = "login" | "signup";

interface OAuthPopupMessage {
    type: "synaptiq_oauth_result";
    status: "success" | "error";
    payload?: AuthResponse;
    error?: AuthError;
}

class AuthService {
    // Local storage keys
    private readonly TOKEN_KEY = "synaptiq_tokens";
    private readonly USER_KEY = "synaptiq_user";

    private getErrorMessage(errorBody: unknown, fallback: string): string {
        if (!errorBody || typeof errorBody !== "object") return fallback;

        const payload = errorBody as { detail?: unknown; message?: unknown };
        if (typeof payload.message === "string") return payload.message;
        if (typeof payload.detail === "string") return payload.detail;

        if (payload.detail && typeof payload.detail === "object") {
            const nested = payload.detail as { message?: unknown };
            if (typeof nested.message === "string") return nested.message;
        }

        return fallback;
    }

    private async parseErrorResponse(res: Response, fallback: string): Promise<string> {
        try {
            const errorBody = await res.json();
            return this.getErrorMessage(errorBody, fallback);
        } catch {
            return fallback;
        }
    }

    private getTokens(): Tokens | null {
        if (typeof window === "undefined") return null;
        try {
            const stored = localStorage.getItem(this.TOKEN_KEY);
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    }

    private setSession(response: AuthResponse) {
        if (typeof window === "undefined") return;
        localStorage.setItem(this.TOKEN_KEY, JSON.stringify(response.tokens));
        localStorage.setItem(this.USER_KEY, JSON.stringify(response.user));
        window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT));
    }

    private clearSession() {
        if (typeof window === "undefined") return;
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
        window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT));
    }

    async signup(data: { email: string; password: string; name?: string }): Promise<AuthResponse> {
        const res = await fetch(`${API_BASE_URL}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        if (!res.ok) {
            throw new Error(await this.parseErrorResponse(res, "Signup failed"));
        }

        const response = await res.json();
        this.setSession(response);
        return response;
    }

    async login(data: { email: string; password: string }): Promise<AuthResponse> {
        const res = await fetch(`${API_BASE_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        if (!res.ok) {
            throw new Error(await this.parseErrorResponse(res, "Login failed"));
        }

        const response = await res.json();
        this.setSession(response);
        return response;
    }

    async oauth(provider: OAuthProvider, mode: OAuthMode = "login"): Promise<AuthResponse> {
        if (typeof window === "undefined") {
            throw new Error("OAuth login is only available in the browser");
        }

        const popupUrl = `${API_BASE_URL}/auth/oauth/${provider}/start?mode=${mode}&origin=${encodeURIComponent(window.location.origin)}`;
        const popup = window.open(
            popupUrl,
            "synaptiq-oauth",
            "width=520,height=700,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes"
        );

        if (!popup) {
            throw new Error("Popup blocked. Please allow popups and try again.");
        }

        return new Promise<AuthResponse>((resolve, reject) => {
            let resolved = false;
            let cleanup = () => {};

            const closeWithError = (message: string) => {
                if (resolved) return;
                resolved = true;
                cleanup();
                reject(new Error(message));
            };

            const closeWithSuccess = (response: AuthResponse) => {
                if (resolved) return;
                resolved = true;
                cleanup();
                this.setSession(response);
                resolve(response);
            };

            const intervalId = window.setInterval(() => {
                if (popup.closed && !resolved) {
                    closeWithError("OAuth login was cancelled.");
                }
            }, 400);

            const timeoutId = window.setTimeout(() => {
                if (!popup.closed) popup.close();
                closeWithError("OAuth login timed out. Please try again.");
            }, 120000);

            const onMessage = (event: MessageEvent<OAuthPopupMessage>) => {
                if (event.origin !== API_ORIGIN) return;
                if (event.source !== popup) return;

                const data = event.data;
                if (!data || data.type !== "synaptiq_oauth_result") return;

                if (data.status === "success" && data.payload) {
                    closeWithSuccess(data.payload);
                    return;
                }

                closeWithError(data.error?.message || "OAuth login failed");
            };

            cleanup = () => {
                window.removeEventListener("message", onMessage);
                window.clearInterval(intervalId);
                window.clearTimeout(timeoutId);
            };

            window.addEventListener("message", onMessage);
        });
    }

    async logout(): Promise<void> {
        const tokens = this.getTokens();

        // Try to notify backend, but always clear local session
        if (tokens?.refresh_token) {
            try {
                await fetch(`${API_BASE_URL}/auth/logout`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
                });
            } catch (e) {
                console.error("Logout API call failed", e);
            }
        }

        this.clearSession();
    }

    async syncCurrentUser(): Promise<User | null> {
        const tokens = this.getTokens();
        if (!tokens?.access_token) return null;

        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, {
                headers: { Authorization: `Bearer ${tokens.access_token}` },
            });

            if (!res.ok) return null;

            const user = (await res.json()) as User;
            if (typeof window !== "undefined") {
                localStorage.setItem(this.USER_KEY, JSON.stringify(user));
                window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT));
            }
            return user;
        } catch {
            return null;
        }
    }

    getUser(): User | null {
        if (typeof window === "undefined") return null;
        const stored = localStorage.getItem(this.USER_KEY);
        return stored ? JSON.parse(stored) : null;
    }

    getAccessToken(): string | null {
        return this.getTokens()?.access_token || null;
    }

    isAuthenticated(): boolean {
        return Boolean(this.getAccessToken());
    }
}

export const authService = new AuthService();
