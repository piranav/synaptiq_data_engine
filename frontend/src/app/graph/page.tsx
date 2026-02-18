"use client";

import { useState, useCallback, useRef } from "react";
import { PoincareDisk } from "@/components/graph/PoincareDisk";
import { GraphSidebar, NodeInfo } from "@/components/graph/GraphSidebar";
import { GraphFiltersPanel } from "@/components/graph/GraphFilters";
import { ArrowLeft, PanelRightOpen, PanelRightClose } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import type { GraphFilters } from "@/lib/api/graph";

export default function GraphPage() {
    const { user } = useAuth();
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [centeredNode, setCenteredNode] = useState<NodeInfo | null>(null);
    const [adjacentNodes, setAdjacentNodes] = useState<NodeInfo[]>([]);
    const [filters, setFilters] = useState<GraphFilters>({});

    // Store the navigation function from PoincareDisk
    const navigateToNodeRef = useRef<((nodeId: string) => void) | null>(null);

    const handleCenterChange = useCallback((node: NodeInfo | null, adjacent: NodeInfo[]) => {
        setCenteredNode(node);
        setAdjacentNodes(adjacent);
    }, []);

    const handleHypertreeReady = useCallback((navigateToNode: (nodeId: string) => void) => {
        navigateToNodeRef.current = navigateToNode;
    }, []);

    const handleSidebarNodeSelect = useCallback((nodeId: string, nodeName: string) => {
        console.log("Navigating to node:", nodeName, nodeId);
        if (navigateToNodeRef.current) {
            navigateToNodeRef.current(nodeId);
        }
    }, []);

    return (
        <div className="w-screen h-screen bg-[#1C1C1E] flex overflow-hidden">
            {/* Main Graph Area */}
            <div className="flex-1 flex flex-col relative">
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

                    {/* Sidebar Toggle */}
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className="pointer-events-auto bg-[#2C2C2E] border border-[#38383A] rounded-xl p-3 shadow-lg hover:bg-[#3C3C3E] transition-colors"
                    >
                        {sidebarOpen ? (
                            <PanelRightClose className="w-5 h-5 text-white/60" />
                        ) : (
                            <PanelRightOpen className="w-5 h-5 text-white/60" />
                        )}
                    </button>
                </div>

                {/* Main Graph Canvas */}
                <div className="flex-1 w-full h-full">
                    <PoincareDisk
                        className="w-full h-full"
                        userName={user?.name ?? undefined}
                        onCenterChange={handleCenterChange}
                        onHypertreeReady={handleHypertreeReady}
                        filters={filters}
                    />
                </div>

                {/* Filter Controls */}
                <GraphFiltersPanel filters={filters} onFiltersChange={setFilters} />
            </div>

            {/* Sidebar */}
            <GraphSidebar
                isOpen={sidebarOpen}
                onClose={() => setSidebarOpen(false)}
                centeredNode={centeredNode}
                adjacentNodes={adjacentNodes}
                onNodeSelect={handleSidebarNodeSelect}
            />
        </div>
    );
}
