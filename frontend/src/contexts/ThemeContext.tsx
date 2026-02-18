"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { type ThemeMode, userService } from "@/lib/api/user";

type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
    themeMode: ThemeMode;
    resolvedTheme: ResolvedTheme;
    setThemeMode: (mode: ThemeMode) => void;
}

const THEME_STORAGE_KEY = "synaptiq_theme_mode";
const VALID_THEME_MODES: ThemeMode[] = ["system", "light", "dark"];

function isThemeMode(value: string | null): value is ThemeMode {
    if (!value) return false;
    return VALID_THEME_MODES.includes(value as ThemeMode);
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
        if (typeof window === "undefined") return "system";
        const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
        return isThemeMode(storedTheme) ? storedTheme : "system";
    });
    const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");

    const persistTheme = useCallback((mode: ThemeMode) => {
        setThemeModeState(mode);
        if (typeof window !== "undefined") {
            localStorage.setItem(THEME_STORAGE_KEY, mode);
        }
    }, []);

    const setThemeMode = useCallback((mode: ThemeMode) => {
        persistTheme(mode);
        userService.updateSettings({ theme: mode }).catch(() => {
            // Non-blocking optimistic update
        });
    }, [persistTheme]);

    useEffect(() => {
        let active = true;

        const storedTheme = typeof window !== "undefined"
            ? localStorage.getItem(THEME_STORAGE_KEY)
            : null;

        const hasToken = (() => {
            if (typeof window === "undefined") return false;
            try {
                const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
                return Boolean(tokens.access_token);
            } catch {
                return false;
            }
        })();

        const hydrateFromServer = async () => {
            if (!hasToken) return;
            try {
                const settings = await userService.getSettings();
                if (!active || !isThemeMode(settings.theme)) {
                    return;
                }

                if (isThemeMode(storedTheme)) {
                    if (storedTheme !== settings.theme) {
                        await userService.updateSettings({ theme: storedTheme });
                    }
                    return;
                }

                persistTheme(settings.theme);
            } catch (error) {
                // Ignore unauthenticated/settings failures silently
                // Only log if it's not an auth error
                if (error instanceof Error && !error.message.includes("token") && !error.message.includes("Authentication")) {
                    console.debug("Theme settings fetch failed:", error.message);
                }
            }
        };

        hydrateFromServer();

        return () => {
            active = false;
        };
    }, [persistTheme]);

    useEffect(() => {
        if (typeof window === "undefined") return;

        const media = window.matchMedia("(prefers-color-scheme: dark)");
        const applyTheme = () => {
            const nextTheme: ResolvedTheme = themeMode === "system"
                ? (media.matches ? "dark" : "light")
                : themeMode;
            setResolvedTheme(nextTheme);
            document.documentElement.setAttribute("data-theme", nextTheme);
        };

        applyTheme();

        if (themeMode !== "system") {
            return;
        }

        media.addEventListener("change", applyTheme);
        return () => {
            media.removeEventListener("change", applyTheme);
        };
    }, [themeMode]);

    const value = useMemo(
        () => ({
            themeMode,
            resolvedTheme,
            setThemeMode,
        }),
        [resolvedTheme, setThemeMode, themeMode],
    );

    return (
        <ThemeContext.Provider value={value}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error("useTheme must be used within ThemeProvider");
    }
    return context;
}
