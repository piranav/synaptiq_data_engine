"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { authService } from "@/lib/api/auth";

export default function SignupPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            const response = await authService.signup({ name, email, password });
            console.log("Signed up:", response);
            window.location.href = "/home";
        } catch (err: any) {
            setError(err.message || "Something went wrong. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <div className="mb-8">
                <h1 className="text-title-1 mb-2">Create an account</h1>
                <p className="text-body text-secondary">
                    Start building your personal knowledge graph today.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-6">
                <Input
                    id="name"
                    type="text"
                    label="Full Name"
                    placeholder="Jane Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    autoFocus
                />

                <Input
                    id="email"
                    type="email"
                    label="Email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />

                <Input
                    id="password"
                    type="password"
                    label="Password"
                    placeholder="Min. 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                />

                {error && (
                    <div className="p-3 rounded-md bg-danger/10 text-danger text-callout">
                        {error}
                    </div>
                )}

                <Button
                    type="submit"
                    size="lg"
                    isLoading={isLoading}
                    className="w-full mt-2"
                >
                    Create Account
                </Button>
            </form>

            <div className="mt-8 flex items-center gap-4">
                <div className="h-px flex-1 bg-border-subtle" />
                <span className="text-callout text-tertiary">or continue with</span>
                <div className="h-px flex-1 bg-border-subtle" />
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4">
                <Button variant="secondary" onClick={() => console.log("Google auth")}>
                    Google
                </Button>
                <Button variant="secondary" onClick={() => console.log("Github auth")}>
                    GitHub
                </Button>
            </div>

            <p className="mt-8 text-center text-callout text-secondary">
                Already have an account?{" "}
                <Link href="/login" className="text-accent hover:underline font-medium">
                    Sign in
                </Link>
            </p>
        </>
    );
}

