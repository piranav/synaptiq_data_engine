"use client";

import { useAuth } from "@/contexts/AuthContext";
import { QuickCapture } from "@/components/dashboard/QuickCapture";
import { StatsRow } from "@/components/dashboard/StatsRow";
import { PoincareDisk } from "@/components/graph/PoincareDisk";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import Link from "next/link";
import { Maximize2 } from "lucide-react";

export default function HomePage() {
    const { user } = useAuth();
    const firstName = user?.name?.split(" ")[0] || "there";

    return (
        <div className="max-w-[1024px] mx-auto px-8 py-10 flex flex-col gap-10 animation-fade-in-up">
            <section>
                <h1 className="text-3xl font-medium tracking-tight text-primary mb-2">Good morning, {firstName}</h1>
                <p className="text-secondary font-normal text-sm">Your graph has grown by 12% this week. Ready to capture?</p>
            </section>

            <QuickCapture />

            <StatsRow />

            <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[500px]">
                <div className="lg:col-span-8 bg-[#1C1C1E] rounded-3xl relative overflow-hidden shadow-lg group cursor-pointer border border-black/5">
                    <div className="absolute top-5 left-5 z-10 flex gap-2">
                        <span className="text-white/40 text-xs font-medium tracking-wide uppercase">Poincaré View</span>
                    </div>
                    <div className="absolute bottom-5 right-5 z-10">
                        <Link href="/graph" className="bg-white/10 backdrop-blur-md text-white/90 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/10 hover:bg-white/20 transition-colors flex items-center gap-2">
                            Expand Graph <Maximize2 className="w-3 h-3" />
                        </Link>
                    </div>
                    <div className="absolute inset-0">
                        <PoincareDisk />
                    </div>
                </div>

                <div className="lg:col-span-4 h-full overflow-hidden">
                    <RecentActivity />
                </div>
            </section>
        </div>
    );
}
