"use client";

import Link from "next/link";
import { PoincareDisk } from "@/components/graph/PoincareDisk";
import { ArrowRight } from "lucide-react";

export function GraphPreview() {
    return (
        <div className="relative w-full h-[300px] rounded-2xl overflow-hidden border border-[#38383A] bg-[#1C1C1E] shadow-sm transform transition-all duration-300 hover:shadow-md group">
            {/* Header / Title Overlay */}
            <div className="absolute top-4 left-4 z-10">
                <h3 className="text-white text-lg font-semibold tracking-tight">Knowledge Graph</h3>
                <p className="text-[#98989D] text-sm">34 concepts • 12 sources</p>
            </div>

            {/* Graph Visualization */}
            <div className="w-full h-full opacity-80 group-hover:opacity-100 transition-opacity duration-300">
                <PoincareDisk
                    centerNode="Neural Networks"
                    isPreview={true}
                    className="pointer-events-none" // or allow minimal interaction
                />
            </div>

            {/* Footer / CTA */}
            <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent flex justify-end">
                <Link
                    href="/graph"
                    className="flex items-center gap-2 text-[#0A84FF] text-sm font-medium hover:text-[#409CFF] transition-colors"
                >
                    Explore Graph <ArrowRight className="w-4 h-4" />
                </Link>
            </div>
        </div>
    );
}
