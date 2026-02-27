"use client";

import { Button } from "@/components/ui/Button";
import { authService } from "@/lib/api/auth";
import { userService, type UserSettings } from "@/lib/api/user";
import {
    LogOut,
    User,
    Settings,
    Database,
    Sun,
    Moon,
    Monitor,
    Key,
    Check,
    Eye,
    EyeOff,
    Loader2,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
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

    // API keys state
    const [settings, setSettings] = useState<UserSettings | null>(null);
    const [openaiKey, setOpenaiKey] = useState("");
    const [anthropicKey, setAnthropicKey] = useState("");
    const [showOpenaiKey, setShowOpenaiKey] = useState(false);
    const [showAnthropicKey, setShowAnthropicKey] = useState(false);
    const [savingOpenai, setSavingOpenai] = useState(false);
    const [savingAnthropic, setSavingAnthropic] = useState(false);
    const [openaiSaved, setOpenaiSaved] = useState(false);
    const [anthropicSaved, setAnthropicSaved] = useState(false);

    const loadSettings = useCallback(async () => {
        try {
            const s = await userService.getSettings();
            setSettings(s);
        } catch (err) {
            console.error("Failed to load settings", err);
        }
    }, []);

    useEffect(() => {
        loadSettings();
    }, [loadSettings]);

    const handleSignOut = async () => {
        setIsSigningOut(true);
        try {
            await authService.logout();
            window.location.href = "/login";
        } catch (error) {
            console.error("Failed to sign out", error);
            window.location.href = "/login";
        } finally {
            setIsSigningOut(false);
        }
    };

    const handleSaveOpenaiKey = async () => {
        setSavingOpenai(true);
        try {
            const updated = await userService.updateSettings({
                openai_api_key: openaiKey,
            });
            setSettings(updated);
            setOpenaiKey("");
            setOpenaiSaved(true);
            setTimeout(() => setOpenaiSaved(false), 2000);
        } catch (err) {
            console.error("Failed to save OpenAI key", err);
        } finally {
            setSavingOpenai(false);
        }
    };

    const handleClearOpenaiKey = async () => {
        setSavingOpenai(true);
        try {
            const updated = await userService.updateSettings({
                openai_api_key: "",
            });
            setSettings(updated);
            setOpenaiKey("");
        } catch (err) {
            console.error("Failed to clear OpenAI key", err);
        } finally {
            setSavingOpenai(false);
        }
    };

    const handleSaveAnthropicKey = async () => {
        setSavingAnthropic(true);
        try {
            const updated = await userService.updateSettings({
                anthropic_api_key: anthropicKey,
            });
            setSettings(updated);
            setAnthropicKey("");
            setAnthropicSaved(true);
            setTimeout(() => setAnthropicSaved(false), 2000);
        } catch (err) {
            console.error("Failed to save Anthropic key", err);
        } finally {
            setSavingAnthropic(false);
        }
    };

    const handleClearAnthropicKey = async () => {
        setSavingAnthropic(true);
        try {
            const updated = await userService.updateSettings({
                anthropic_api_key: "",
            });
            setSettings(updated);
            setAnthropicKey("");
        } catch (err) {
            console.error("Failed to clear Anthropic key", err);
        } finally {
            setSavingAnthropic(false);
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

                {/* API Keys Section */}
                <section className="bg-surface border border-border rounded-xl overflow-hidden shadow-card">
                    <div className="px-6 py-4 border-b border-border bg-canvas/30 flex items-center gap-3">
                        <Key className="w-5 h-5 text-secondary" />
                        <h2 className="text-title-3">API Keys</h2>
                    </div>
                    <div className="p-6 space-y-6">
                        <p className="text-body-small text-secondary">
                            Add your own API keys to use additional models. Keys are stored securely and never shared.
                        </p>

                        {/* OpenAI Key */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-body font-medium">OpenAI</p>
                                    <p className="text-body-small text-secondary">
                                        Use your own key for GPT models.
                                        {settings?.openai_api_key_set && (
                                            <span className="ml-2 inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                                                <Check className="w-3 h-3" /> Key saved
                                            </span>
                                        )}
                                    </p>
                                </div>
                                {settings?.openai_api_key_set && (
                                    <button
                                        onClick={handleClearOpenaiKey}
                                        disabled={savingOpenai}
                                        className="text-[12px] text-danger hover:text-danger/80 underline"
                                    >
                                        Remove
                                    </button>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <input
                                        type={showOpenaiKey ? "text" : "password"}
                                        value={openaiKey}
                                        onChange={(e) => setOpenaiKey(e.target.value)}
                                        placeholder={settings?.openai_api_key_set ? "••••••••••••••••••••" : "sk-..."}
                                        className="w-full h-9 pl-3 pr-9 rounded-md border border-border bg-canvas text-[13px] text-primary placeholder:text-secondary outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowOpenaiKey(!showOpenaiKey)}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-secondary hover:text-primary"
                                    >
                                        {showOpenaiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={handleSaveOpenaiKey}
                                    disabled={!openaiKey.trim() || savingOpenai}
                                >
                                    {savingOpenai ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : openaiSaved ? (
                                        <Check className="w-4 h-4 text-green-500" />
                                    ) : (
                                        "Save"
                                    )}
                                </Button>
                            </div>
                        </div>

                        <div className="h-px bg-border-subtle" />

                        {/* Anthropic Key */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-body font-medium">Anthropic</p>
                                    <p className="text-body-small text-secondary">
                                        Required for Claude models.
                                        {settings?.anthropic_api_key_set && (
                                            <span className="ml-2 inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                                                <Check className="w-3 h-3" /> Key saved
                                            </span>
                                        )}
                                    </p>
                                </div>
                                {settings?.anthropic_api_key_set && (
                                    <button
                                        onClick={handleClearAnthropicKey}
                                        disabled={savingAnthropic}
                                        className="text-[12px] text-danger hover:text-danger/80 underline"
                                    >
                                        Remove
                                    </button>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <input
                                        type={showAnthropicKey ? "text" : "password"}
                                        value={anthropicKey}
                                        onChange={(e) => setAnthropicKey(e.target.value)}
                                        placeholder={settings?.anthropic_api_key_set ? "••••••••••••••••••••" : "sk-ant-..."}
                                        className="w-full h-9 pl-3 pr-9 rounded-md border border-border bg-canvas text-[13px] text-primary placeholder:text-secondary outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowAnthropicKey(!showAnthropicKey)}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-secondary hover:text-primary"
                                    >
                                        {showAnthropicKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={handleSaveAnthropicKey}
                                    disabled={!anthropicKey.trim() || savingAnthropic}
                                >
                                    {savingAnthropic ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : anthropicSaved ? (
                                        <Check className="w-4 h-4 text-green-500" />
                                    ) : (
                                        "Save"
                                    )}
                                </Button>
                            </div>
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
