"use client";

import { QuickCapture } from "@/components/dashboard/QuickCapture";
import { StatsRow } from "@/components/dashboard/StatsRow";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { PoincareDisk } from "@/components/graph/PoincareDisk";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function HomePage() {
    const { user } = useAuth();
    const firstName = user?.name?.split(" ")[0] || "there";

    return (
        <div className="max-w-[960px] mx-auto w-full animation-fade-in-up">
            <h1 className="text-title-1 mb-8">Good morning, {firstName}</h1>

            <QuickCapture />

            <StatsRow />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-8">
                    {/* Knowledge Preview */}
                    <div className="bg-[#1C1C1E] rounded-xl overflow-hidden shadow-card h-[280px] relative group cursor-pointer">
                        <div className="absolute inset-0">
                            <PoincareDisk />
                        </div>
                        <div className="absolute bottom-4 right-4 z-10">
                            <Link href="/graph" className="px-4 py-2 bg-white/10 backdrop-blur-md rounded-full text-white text-callout hover:bg-white/20 transition-colors border border-white/10 flex items-center gap-2">
                                View graph <span>→</span>
                            </Link>
                        </div>
                        <div className="absolute top-4 left-4 z-10">
                            <span className="px-2 py-1 bg-black/50 backdrop-blur rounded text-white text-caption">
                                Live Preview
                            </span>
                        </div>
                    </div>

                    <RecentActivity />
                </div>

                <div className="space-y-6">
                    <div className="bg-surface border border-border rounded-xl p-5 shadow-card">
                        <h3 className="text-title-3 mb-2">Suggested Actions</h3>
                        <ul className="space-y-3">
                            <li className="flex items-center gap-3 text-body-small text-secondary hover:text-primary cursor-pointer transition-colors p-2 hover:bg-canvas rounded-lg -mx-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                                Complete your profile
                            </li>
                            <li className="flex items-center gap-3 text-body-small text-secondary hover:text-primary cursor-pointer transition-colors p-2 hover:bg-canvas rounded-lg -mx-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                                Review 3 pending concepts
                            </li>
                            <li className="flex items-center gap-3 text-body-small text-secondary hover:text-primary cursor-pointer transition-colors p-2 hover:bg-canvas rounded-lg -mx-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-success" />
                                Sync with Obsidian
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
}
