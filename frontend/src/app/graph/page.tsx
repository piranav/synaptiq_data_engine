"use client";

import { PoincareDisk } from "@/components/graph/PoincareDisk";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function GraphPage() {
    const { user } = useAuth();

    return (
        <div className="w-screen h-screen bg-[#1C1C1E] flex flex-col overflow-hidden">
            {/* Header Overlay */}
            <div className="absolute top-0 left-0 right-0 p-6 z-20 flex justify-between items-start pointer-events-none">
                <div className="pointer-events-auto">
                    <Link href="/home" className="flex items-center gap-2 text-white/60 hover:text-white transition-colors mb-4">
                        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
                    </Link>
                    <h1 className="text-2xl font-semibold text-white tracking-tight">Knowledge Graph</h1>
                    <p className="text-white/40 text-sm mt-1">
                        Explore concepts and their relationships
                    </p>
                </div>

                {/* Controls (Placeholder) */}
                <div className="bg-[#2C2C2E] border border-[#38383A] rounded-xl p-2 pointer-events-auto shadow-lg">
                    {/* Filter controls could go here */}
                    <div className="text-xs text-center text-white/40 px-2">
                        {user?.name}'s Ontology
                    </div>
                </div>
            </div>

            {/* Interaction Hint */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-[#2C2C2E]/80 backdrop-blur text-white/60 text-xs px-4 py-2 rounded-full border border-white/5 pointer-events-none z-10">
                Click to center • Scroll to zoom • Drag to pan
            </div>

            {/* Main Graph Canvas */}
            <div className="flex-1 w-full h-full">
                {/* Passing centerNode null means it will default to root or fetch general graph */}
                <PoincareDisk className="w-full h-full" />
            </div>
        </div>
    );
}
