import { z } from "zod";

const API_BASE_URL = "http://localhost:8000/api/v1";

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

class AuthService {
    // Local storage keys
    private readonly TOKEN_KEY = "synaptiq_tokens";
    private readonly USER_KEY = "synaptiq_user";

    private getTokens(): Tokens | null {
        if (typeof window === "undefined") return null;
        const stored = localStorage.getItem(this.TOKEN_KEY);
        return stored ? JSON.parse(stored) : null;
    }

    private setSession(response: AuthResponse) {
        if (typeof window === "undefined") return;
        localStorage.setItem(this.TOKEN_KEY, JSON.stringify(response.tokens));
        localStorage.setItem(this.USER_KEY, JSON.stringify(response.user));
    }

    private clearSession() {
        if (typeof window === "undefined") return;
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
    }

    async signup(data: { email: string; password: string; name?: string }): Promise<AuthResponse> {
        const res = await fetch(`${API_BASE_URL}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail?.message || "Signup failed");
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
            const error = await res.json();
            throw new Error(error.detail?.message || "Login failed");
        }

        const response = await res.json();
        this.setSession(response);
        return response;
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

    getUser(): User | null {
        if (typeof window === "undefined") return null;
        const stored = localStorage.getItem(this.USER_KEY);
        return stored ? JSON.parse(stored) : null;
    }
}

export const authService = new AuthService();
