"use client";

import Link from "next/link";
import { Maximize2 } from "lucide-react";
import { PoincareDisk } from "@/components/graph/PoincareDisk";

export function GraphSpotlight() {
    return (
        <section className="relative dashboard-card rounded-[30px] min-h-[440px] overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_14%,rgba(224,102,67,0.12),transparent_48%)] pointer-events-none" />
            <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-5 py-4">
                <div>
                    <p className="text-[11px] uppercase tracking-[0.14em] text-secondary font-semibold">Graph Spotlight</p>
                    <h2 className="text-lg font-semibold text-primary mt-1">Poincare view of your current graph</h2>
                </div>
                <Link
                    href="/graph"
                    className="dashboard-pill inline-flex items-center gap-2 px-3.5 py-2 text-xs text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-colors"
                >
                    Open Graph <Maximize2 className="w-3.5 h-3.5" />
                </Link>
            </div>

            <div className="absolute inset-0 pt-14">
                <PoincareDisk />
            </div>
        </section>
    );
}
