"use client";

import { api } from "./client";

export type ThemeMode = "light" | "dark" | "system";

export interface UserSettings {
    theme: ThemeMode;
    accent_color: string;
    sidebar_collapsed: boolean;
    density: "comfortable" | "compact";
    processing_mode: "cloud" | "on_device";
    analytics_opt_in: boolean;
    openai_api_key_set: boolean;
    anthropic_api_key_set: boolean;
    preferred_model: string;
}

export interface ModelInfo {
    id: string;
    name: string;
    provider: string;
    description: string;
    requires_key: boolean;
}

class UserService {
    async getSettings(): Promise<UserSettings> {
        const { data } = await api.get<UserSettings>("/user/settings");
        return data;
    }

    async updateSettings(
        patch: Partial<
            Pick<
                UserSettings,
                | "theme"
                | "accent_color"
                | "sidebar_collapsed"
                | "density"
                | "processing_mode"
                | "analytics_opt_in"
                | "preferred_model"
            > & {
                openai_api_key?: string;
                anthropic_api_key?: string;
            }
        >
    ): Promise<UserSettings> {
        const { data } = await api.patch<UserSettings>("/user/settings", patch);
        return data;
    }

    async listModels(): Promise<ModelInfo[]> {
        const { data } = await api.get<ModelInfo[]>("/user/models");
        return data;
    }
}

export const userService = new UserService();
