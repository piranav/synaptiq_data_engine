"use client";

import { Button } from "@/components/ui/Button";
import { authService } from "@/lib/api/auth";
import { userService, type ApiKeysStatus } from "@/lib/api/user";
import { LogOut, User, Settings, Database, Sun, Moon, Monitor, Key, Eye, EyeOff, Check, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import clsx from "clsx";
import { useTheme } from "@/contexts/ThemeContext";

const themeOptions = [
    { value: "system", label: "System", icon: Monitor },
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
] as const;

function ApiKeyInput({
    label,
    placeholder,
    value,
    onChange,
    maskedValue,
    isSet,
    isSaving,
    onSave,
    onClear,
}: {
    label: string;
    placeholder: string;
    value: string;
    onChange: (v: string) => void;
    maskedValue: string;
    isSet: boolean;
    isSaving: boolean;
    onSave: () => void;
    onClear: () => void;
}) {
    const [showKey, setShowKey] = useState(false);
    const [editing, setEditing] = useState(false);

    const displayValue = editing ? value : "";

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <p className="text-body font-medium">{label}</p>
                {isSet && !editing && (
                    <span className="inline-flex items-center gap-1 text-[12px] leading-[16px] text-green-500 font-medium">
                        <Check className="w-3.5 h-3.5" />
                        Configured
                    </span>
                )}
            </div>
            {isSet && !editing ? (
                <div className="flex items-center gap-2">
                    <div className="flex-1 h-10 px-3 rounded-lg border border-border bg-canvas/50 flex items-center text-[13px] text-secondary font-mono">
                        {maskedValue || "****...****"}
                    </div>
                    <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                        Change
                    </Button>
                    <Button variant="danger" size="sm" onClick={onClear}>
                        Remove
                    </Button>
                </div>
            ) : (
                <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                        <input
                            type={showKey ? "text" : "password"}
                            value={displayValue}
                            onChange={(e) => onChange(e.target.value)}
                            placeholder={placeholder}
                            className="w-full h-10 px-3 pr-10 rounded-lg border border-border bg-canvas/50 text-[13px] text-primary placeholder:text-secondary font-mono outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/45 transition-all"
                        />
                        <button
                            type="button"
                            onClick={() => setShowKey(!showKey)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-secondary hover:text-primary"
                        >
                            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                    </div>
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                            onSave();
                            setEditing(false);
                        }}
                        isLoading={isSaving}
                        disabled={!value.trim()}
                    >
                        Save
                    </Button>
                    {isSet && (
                        <Button variant="secondary" size="sm" onClick={() => { setEditing(false); onChange(""); }}>
                            Cancel
                        </Button>
                    )}
                </div>
            )}
        </div>
    );
}

export default function SettingsPage() {
    const [isSigningOut, setIsSigningOut] = useState(false);
    const { themeMode, resolvedTheme, setThemeMode } = useTheme();

    const [apiKeys, setApiKeys] = useState<ApiKeysStatus | null>(null);
    const [openaiKey, setOpenaiKey] = useState("");
    const [anthropicKey, setAnthropicKey] = useState("");
    const [isSavingOpenai, setIsSavingOpenai] = useState(false);
    const [isSavingAnthropic, setIsSavingAnthropic] = useState(false);

    useEffect(() => {
        userService.getApiKeys().then(setApiKeys).catch(() => {});
    }, []);

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

    const saveOpenaiKey = async () => {
        setIsSavingOpenai(true);
        try {
            const updated = await userService.saveApiKeys({ openai_api_key: openaiKey });
            setApiKeys(updated);
            setOpenaiKey("");
        } catch (e) {
            console.error("Failed to save OpenAI key", e);
        } finally {
            setIsSavingOpenai(false);
        }
    };

    const saveAnthropicKey = async () => {
        setIsSavingAnthropic(true);
        try {
            const updated = await userService.saveApiKeys({ anthropic_api_key: anthropicKey });
            setApiKeys(updated);
            setAnthropicKey("");
        } catch (e) {
            console.error("Failed to save Anthropic key", e);
        } finally {
            setIsSavingAnthropic(false);
        }
    };

    const clearKey = async (provider: "openai" | "anthropic") => {
        const body = provider === "openai"
            ? { openai_api_key: "" }
            : { anthropic_api_key: "" };
        try {
            const updated = await userService.saveApiKeys(body);
            setApiKeys(updated);
        } catch (e) {
            console.error(`Failed to clear ${provider} key`, e);
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
                            Add your own API keys to use different LLM providers. Keys are encrypted before storage.
                        </p>

                        <ApiKeyInput
                            label="OpenAI API Key"
                            placeholder="sk-..."
                            value={openaiKey}
                            onChange={setOpenaiKey}
                            maskedValue={apiKeys?.openai_api_key_masked || ""}
                            isSet={apiKeys?.openai_api_key_set || false}
                            isSaving={isSavingOpenai}
                            onSave={saveOpenaiKey}
                            onClear={() => clearKey("openai")}
                        />

                        <div className="h-px bg-border-subtle" />

                        <ApiKeyInput
                            label="Anthropic API Key"
                            placeholder="sk-ant-..."
                            value={anthropicKey}
                            onChange={setAnthropicKey}
                            maskedValue={apiKeys?.anthropic_api_key_masked || ""}
                            isSet={apiKeys?.anthropic_api_key_set || false}
                            isSaving={isSavingAnthropic}
                            onSave={saveAnthropicKey}
                            onClear={() => clearKey("anthropic")}
                        />
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
