import { PoincareDisk } from "@/components/graph/PoincareDisk";
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
            <div className="hidden lg:flex w-1/2 bg-[#1C1C1E] relative flex-col items-center justify-center p-12 text-white overflow-hidden">
                <div className="absolute inset-0 z-0">
                    <PoincareDisk />
                </div>

                <div className="relative z-10 max-w-lg text-center">
                    <h2 className="text-display mb-6 tracking-tight">Synaptiq</h2>
                    <p className="text-title-2 text-white/60 font-normal">
                        Where your knowledge takes shape in hyperbolic space.
                    </p>
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

                <div className="flex-1 flex flex-col justify-center px-8 sm:px-12 md:px-20 lg:px-[80px] max-w-[640px] mx-auto w-full">
                    {children}
                </div>

                <div className="py-6 text-center text-callout text-tertiary">
                    &copy; {new Date().getFullYear()} Synaptiq. All rights reserved.
                </div>
            </div>
        </div>
    );
}
