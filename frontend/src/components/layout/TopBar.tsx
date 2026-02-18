"use client";

import { Monitor, Moon, Search, Sun, Plus, Mic } from "lucide-react";
import clsx from "clsx";
import { useTheme } from "@/contexts/ThemeContext";

const themeItems = [
    { mode: "light", label: "Light", icon: Sun },
    { mode: "dark", label: "Dark", icon: Moon },
    { mode: "system", label: "System", icon: Monitor },
] as const;

export function TopBar() {
    const { themeMode, setThemeMode } = useTheme();

    return (
        <header className="sticky top-0 z-10 bg-[var(--glass-bg)] border-b border-border px-5 md:px-8 h-[var(--topbar-height)] flex items-center justify-between backdrop-blur-sm">
            <div className="flex items-center gap-3">
                <button
                    type="button"
                    aria-label="Create new item"
                    className="h-10 w-10 rounded-full border border-border bg-surface text-primary hover:bg-[var(--hover-bg)] transition-colors inline-flex items-center justify-center"
                >
                    <Plus className="w-4 h-4" strokeWidth={1.8} />
                </button>
                <div className="dashboard-pill h-10 px-3 gap-2 w-[160px] sm:w-[260px] md:w-[340px]">
                    <Search className="w-4 h-4 text-secondary" strokeWidth={1.7} />
                    <input
                        type="search"
                        placeholder="Start searching here..."
                        className="w-full bg-transparent text-sm text-primary placeholder:text-secondary outline-none"
                    />
                </div>
            </div>

            <div className="flex items-center gap-2">
                <div className="dashboard-pill p-1 gap-1">
                    {themeItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = themeMode === item.mode;
                        return (
                            <button
                                key={item.mode}
                                onClick={() => setThemeMode(item.mode)}
                                title={item.label}
                                aria-label={item.label}
                                className={clsx(
                                    "h-8 w-8 rounded-full inline-flex items-center justify-center transition-colors",
                                    isActive
                                        ? "bg-surface text-primary border border-border shadow-card"
                                        : "text-secondary hover:text-primary hover:bg-[var(--hover-bg)]"
                                )}
                            >
                                <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                            </button>
                        );
                    })}
                </div>
                <button
                    type="button"
                    aria-label="Voice input"
                    className="h-10 w-10 rounded-full border border-border bg-surface text-primary hover:bg-[var(--hover-bg)] transition-colors inline-flex items-center justify-center"
                >
                    <Mic className="w-4 h-4" strokeWidth={1.8} />
                </button>
            </div>
        </header>
    );
}
