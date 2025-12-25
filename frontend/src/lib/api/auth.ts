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

        return res.json();
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

        return res.json();
    }
}

export const authService = new AuthService();
