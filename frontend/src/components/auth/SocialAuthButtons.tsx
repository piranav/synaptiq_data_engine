"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { authService, OAuthMode, OAuthProvider } from "@/lib/api/auth";
import { GitHubIcon, GoogleIcon } from "./SocialProviderIcons";

interface SocialAuthButtonsProps {
    mode: OAuthMode;
    onSuccess: () => void;
    onError?: (message: string | null) => void;
}

const PROVIDERS: Array<{
    id: OAuthProvider;
    label: string;
    Icon: typeof GoogleIcon;
}> = [
    { id: "google", label: "Google", Icon: GoogleIcon },
    { id: "github", label: "GitHub", Icon: GitHubIcon },
];

export function SocialAuthButtons({ mode, onSuccess, onError }: SocialAuthButtonsProps) {
    const [loadingProvider, setLoadingProvider] = useState<OAuthProvider | null>(null);

    const handleOAuth = async (provider: OAuthProvider) => {
        setLoadingProvider(provider);
        onError?.(null);

        try {
            await authService.oauth(provider, mode);
            onSuccess();
        } catch (error) {
            const message = error instanceof Error ? error.message : "Social authentication failed";
            onError?.(message);
        } finally {
            setLoadingProvider(null);
        }
    };

    return (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {PROVIDERS.map(({ id, label, Icon }) => (
                <Button
                    key={id}
                    variant="secondary"
                    className="h-[52px] w-full justify-start gap-3 border-white/15 bg-white/[0.02] px-4 text-primary hover:border-white/30 hover:bg-white/[0.06]"
                    isLoading={loadingProvider === id}
                    onClick={() => handleOAuth(id)}
                    disabled={Boolean(loadingProvider)}
                    aria-label={`${mode === "signup" ? "Sign up" : "Sign in"} with ${label}`}
                >
                    <Icon className="h-5 w-5 shrink-0" />
                    <span>Continue with {label}</span>
                </Button>
            ))}
        </div>
    );
}
