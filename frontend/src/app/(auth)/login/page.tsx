"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SocialAuthButtons } from "@/components/auth/SocialAuthButtons";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { authService } from "@/lib/api/auth";

export default function LoginPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            await authService.login({ email, password });
            router.replace("/home");
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Invalid email or password";
            setError(message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="w-full animation-fade-in-up">
            <div className="mb-8">
                <h1 className="text-title-1 mb-2">Welcome back</h1>
                <p className="text-body text-secondary">
                    Enter your credentials to access your graph.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-6">
                <Input
                    id="email"
                    type="email"
                    label="Email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                />

                <div className="flex flex-col gap-2">
                    <Input
                        id="password"
                        type="password"
                        label="Password"
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                    <div className="flex justify-end">
                        <Link
                            href="/forgot-password"
                            className="text-callout text-accent hover:underline"
                        >
                            Forgot password?
                        </Link>
                    </div>
                </div>

                {error && (
                    <div className="p-3 rounded-md bg-danger/10 text-danger text-callout">
                        {error}
                    </div>
                )}

                <Button
                    type="submit"
                    size="lg"
                    isLoading={isLoading}
                    className="mt-2 w-full bg-gradient-to-r from-accent to-[#4f8cff] shadow-[0_10px_28px_rgba(37,107,238,0.35)] hover:from-[#2a74ff] hover:to-[#6ca1ff]"
                >
                    Sign In
                </Button>
            </form>

            <div className="mt-8 flex items-center gap-4">
                <div className="h-px flex-1 bg-border-subtle" />
                <span className="text-callout text-tertiary">or continue with</span>
                <div className="h-px flex-1 bg-border-subtle" />
            </div>

            <SocialAuthButtons
                mode="login"
                onSuccess={() => router.replace("/home")}
                onError={setError}
            />

            <p className="mt-8 text-center text-callout text-secondary">
                Don&apos;t have an account?{" "}
                <Link href="/signup" className="text-accent hover:underline font-medium">
                    Sign up
                </Link>
            </p>
        </div>
    );
}
