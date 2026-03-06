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
}

export interface ApiKeysStatus {
    openai_api_key_set: boolean;
    openai_api_key_masked: string;
    anthropic_api_key_set: boolean;
    anthropic_api_key_masked: string;
}

export interface ChatModel {
    id: string;
    display_name: string;
    provider: "openai" | "anthropic";
    is_reasoning: boolean;
}

class UserService {
    async getSettings(): Promise<UserSettings> {
        const { data } = await api.get<UserSettings>("/user/settings");
        return data;
    }

    async updateSettings(
        patch: Partial<Pick<UserSettings, "theme" | "accent_color" | "sidebar_collapsed" | "density" | "processing_mode" | "analytics_opt_in">>
    ): Promise<UserSettings> {
        const { data } = await api.patch<UserSettings>("/user/settings", patch);
        return data;
    }

    async getApiKeys(): Promise<ApiKeysStatus> {
        const { data } = await api.get<ApiKeysStatus>("/user/api-keys");
        return data;
    }

    async saveApiKeys(keys: {
        openai_api_key?: string;
        anthropic_api_key?: string;
    }): Promise<ApiKeysStatus> {
        const { data } = await api.put<ApiKeysStatus>("/user/api-keys", keys);
        return data;
    }

    async listModels(): Promise<ChatModel[]> {
        const { data } = await api.get<{ models: ChatModel[] }>("/chat/models");
        return data.models;
    }
}

export const userService = new UserService();
