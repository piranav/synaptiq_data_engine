"use client";

import { Button } from "@/components/ui/Button";
import { authService } from "@/lib/api/auth";
import { LogOut, User, Settings, Database, Sun, Moon, Monitor } from "lucide-react";
import { useState } from "react";
import clsx from "clsx";
import { useTheme } from "@/contexts/ThemeContext";

const themeOptions = [
    { value: "system", label: "System", icon: Monitor },
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
] as const;

export default function SettingsPage() {
    const [isSigningOut, setIsSigningOut] = useState(false);
    const { themeMode, resolvedTheme, setThemeMode } = useTheme();

    const handleSignOut = async () => {
        setIsSigningOut(true);
        try {
            await authService.logout();
            window.location.href = "/login";
        } catch (error) {
            console.error("Failed to sign out", error);
            // Force redirect even if API fails
            window.location.href = "/login";
        } finally {
            setIsSigningOut(false);
        }
    };

    return (
        <div className="max-w-[720px] mx-auto animation-fade-in-up">
            <h1 className="text-title-1 mb-2">Settings</h1>
            <p className="text-body text-secondary mb-8">
                Manage your account and preferences.
            </p>

            <div className="space-y-8">
                {/* Account Section */}
                <section className="bg-surface border border-border rounded-xl overflow-hidden shadow-card">
                    <div className="px-6 py-4 border-b border-border bg-canvas/30 flex items-center gap-3">
                        <User className="w-5 h-5 text-secondary" />
                        <h2 className="text-title-3">Account</h2>
                    </div>
                    <div className="p-6 space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-body font-medium">Profile</p>
                                <p className="text-body-small text-secondary">Manage your personal information</p>
                            </div>
                            <Button variant="secondary" size="sm">Edit</Button>
                        </div>

                        <div className="h-px bg-border-subtle" />

                        <div className="flex items-center justify-between">
                            <div className="text-danger">
                                <p className="text-body font-medium">Sign Out</p>
                                <p className="text-body-small text-danger/70">Sign out of your account on this device</p>
                            </div>
                            <Button
                                variant="danger"
                                onClick={handleSignOut}
                                isLoading={isSigningOut}
                            >
                                <LogOut className="w-4 h-4 mr-2" />
                                Sign Out
                            </Button>
                        </div>
                    </div>
                </section>

                {/* Appearance Section */}
                <section className="bg-surface border border-border rounded-xl overflow-hidden shadow-card">
                    <div className="px-6 py-4 border-b border-border bg-canvas/30 flex items-center gap-3">
                        <Settings className="w-5 h-5 text-secondary" />
                        <h2 className="text-title-3">Appearance</h2>
                    </div>
                    <div className="p-6 space-y-4">
                        <div>
                            <p className="text-body font-medium">Theme</p>
                            <p className="text-body-small text-secondary">
                                Choose how Synaptiq looks. Current applied theme: <span className="text-primary capitalize">{resolvedTheme}</span>.
                            </p>
                        </div>
                        <div className="inline-flex rounded-lg border border-border p-1 bg-canvas/30">
                            {themeOptions.map((option) => {
                                const Icon = option.icon;
                                const isActive = themeMode === option.value;
                                return (
                                    <button
                                        key={option.value}
                                        onClick={() => setThemeMode(option.value)}
                                        className={clsx(
                                            "h-9 px-3 rounded-md inline-flex items-center gap-2 text-sm transition-colors",
                                            isActive
                                                ? "bg-elevated text-primary border border-border"
                                                : "text-secondary hover:text-primary hover:bg-[var(--hover-bg)]"
                                        )}
                                    >
                                        <Icon className="w-4 h-4" />
                                        {option.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </section>

                {/* Data Section */}
                <section className="bg-surface border border-border rounded-xl overflow-hidden shadow-card">
                    <div className="px-6 py-4 border-b border-border bg-canvas/30 flex items-center gap-3">
                        <Database className="w-5 h-5 text-secondary" />
                        <h2 className="text-title-3">Data & Storage</h2>
                    </div>
                    <div className="p-6">
                        <p className="text-body-small text-secondary">Graph export options coming soon.</p>
                    </div>
                </section>
            </div>
        </div>
    );
}
