"use client";

import { useState, useCallback, useRef } from "react";
import { PoincareDisk } from "@/components/graph/PoincareDisk";
import { GraphSidebar, NodeInfo } from "@/components/graph/GraphSidebar";
import { GraphFiltersPanel } from "@/components/graph/GraphFilters";
import { ArrowLeft, PanelRightOpen, PanelRightClose } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import type { GraphFilters } from "@/lib/api/graph";
import { GridFrame } from "@/components/layout/GridFrame";

export default function GraphPage() {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [centeredNode, setCenteredNode] = useState<NodeInfo | null>(null);
  const [adjacentNodes, setAdjacentNodes] = useState<NodeInfo[]>([]);
  const [filters, setFilters] = useState<GraphFilters>({});

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
    <div className="relative w-screen h-screen bg-[var(--canvas)] app-grid-bg flex overflow-hidden">
      <GridFrame className="hidden lg:block" />

      <div className="relative z-[2] flex-1 flex flex-col">
        <div className="absolute top-0 left-0 right-0 p-4 md:p-6 z-20 flex justify-between items-start pointer-events-none">
          <div className="pointer-events-auto dashboard-card px-4 py-3 max-w-[380px]">
            <Link href="/home" className="inline-flex items-center gap-2 text-secondary hover:text-primary transition-colors text-sm mb-2">
              <ArrowLeft className="w-4 h-4" /> Back to Dashboard
            </Link>
            <h1 className="text-title-2 font-semibold tracking-tight text-primary">Knowledge Graph</h1>
            <p className="text-secondary text-sm mt-1">Explore concepts and relationships in a dynamic hyperbolic map.</p>
          </div>

          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="pointer-events-auto border border-border rounded-xl p-3 shadow-card bg-surface hover:bg-[var(--hover-bg)] transition-colors"
          >
            {sidebarOpen ? <PanelRightClose className="w-5 h-5 text-secondary" /> : <PanelRightOpen className="w-5 h-5 text-secondary" />}
          </button>
        </div>

        <div className="flex-1 w-full h-full">
          <PoincareDisk
            className="w-full h-full"
            userName={user?.name ?? undefined}
            onCenterChange={handleCenterChange}
            onHypertreeReady={handleHypertreeReady}
            filters={filters}
          />
        </div>

        <GraphFiltersPanel filters={filters} onFiltersChange={setFilters} />
      </div>

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
