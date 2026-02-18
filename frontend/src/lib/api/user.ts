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
}

export const userService = new UserService();
