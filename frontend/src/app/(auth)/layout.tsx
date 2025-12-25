import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen w-full">
            {/* Left Panel - Visual */}
            <div className="hidden lg:flex w-1/2 bg-[#0A0A0A] relative flex-col items-center justify-center p-12 text-white overflow-hidden">
                {/* Decorative dots pattern */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative w-[400px] h-[400px]">
                        {/* Animated orbital dots */}
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-64 h-64 rounded-full border border-white/5" />
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-48 h-48 rounded-full border border-white/5" />
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-32 h-32 rounded-full border border-white/5" />
                        </div>

                        {/* Glowing dots */}
                        <div className="absolute top-1/4 left-1/4 w-2 h-2 bg-accent rounded-full shadow-lg shadow-accent/50 animate-pulse" />
                        <div className="absolute top-1/3 right-1/3 w-3 h-3 bg-node-concept rounded-full shadow-lg shadow-node-concept/50 animate-pulse" style={{ animationDelay: '0.5s' }} />
                        <div className="absolute bottom-1/3 left-1/3 w-2.5 h-2.5 bg-node-source rounded-full shadow-lg shadow-node-source/50 animate-pulse" style={{ animationDelay: '1s' }} />
                        <div className="absolute bottom-1/4 right-1/4 w-2 h-2 bg-node-definition rounded-full shadow-lg shadow-node-definition/50 animate-pulse" style={{ animationDelay: '1.5s' }} />
                        <div className="absolute top-1/2 left-1/5 w-1.5 h-1.5 bg-white/60 rounded-full animate-pulse" style={{ animationDelay: '0.3s' }} />
                        <div className="absolute top-2/5 right-1/5 w-1.5 h-1.5 bg-white/40 rounded-full animate-pulse" style={{ animationDelay: '0.8s' }} />

                        {/* Center glow */}
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-4 h-4 bg-accent/80 rounded-full shadow-2xl shadow-accent/60" />
                        </div>
                    </div>
                </div>

                {/* Quote */}
                <div className="relative z-10 max-w-sm text-center mt-64">
                    <blockquote className="text-title-3 text-white/90 font-light leading-relaxed">
                        &ldquo;The most powerful tool for thought is the one that connects your ideas.&rdquo;
                    </blockquote>
                    <div className="mt-6 w-8 h-px bg-white/20 mx-auto" />
                    <p className="mt-4 text-callout text-white/40">Synaptiq</p>
                </div>
            </div>

            {/* Right Panel - Form */}
            <div className="flex w-full lg:w-1/2 flex-col bg-surface relative">
                <div className="absolute top-8 left-8">
                    <Link href="/" className="inline-flex items-center text-secondary hover:text-primary transition-colors gap-2 text-body-small">
                        <ArrowLeft className="w-4 h-4" />
                        Back to Home
                    </Link>
                </div>

                <div className="flex-1 flex flex-col justify-center px-8 sm:px-12 md:px-20 lg:px-[80px] pt-24 pb-8 max-w-[640px] mx-auto w-full">
                    {children}
                </div>

                <div className="py-6 text-center text-callout text-tertiary">
                    &copy; {new Date().getFullYear()} Synaptiq. All rights reserved.
                </div>
            </div>
        </div>
    );
}

