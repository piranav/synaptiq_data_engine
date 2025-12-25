"use client";

import { useEffect, useRef, useState, useId, useCallback } from "react";
import { graphApi, GraphNeighborhood } from "@/lib/api/graph";
import { transformToJITFormat } from "@/lib/graph/adapter";

// We need to tell TS about $jit on window if we import it
declare global {
    interface Window {
        $jit: any;
    }
}

interface PoincareDiskProps {
    centerNode?: string | null;
    onNodeClick?: (nodeId: string, nodeLabel: string) => void;
    className?: string;
    isPreview?: boolean;
}

export function PoincareDisk({ centerNode: initialCenterNode, onNodeClick, className, isPreview = false }: PoincareDiskProps) {
    const uniqueId = useId();
    // Remove colons and create a clean ID (no spaces - invalid in HTML IDs)
    const containerId = useRef(`infovis-${uniqueId.replace(/:/g, "")}`);
    const [jitLoaded, setJitLoaded] = useState(false);
    const [currentCenter, setCurrentCenter] = useState<string | null>(initialCenterNode || null);
    const [navigationStack, setNavigationStack] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const htRef = useRef<any>(null);
    const graphDataCache = useRef<Map<string, GraphNeighborhood>>(new Map());

    // Load JIT library
    useEffect(() => {
        const loadJit = async () => {
            try {
                // @ts-ignore
                await import('@/lib/jit');
                if (window.$jit) {
                    setJitLoaded(true);
                }
            } catch (e) {
                console.error("Failed to load JIT library", e);
            }
        };
        loadJit();
    }, []);

    // Fetch neighborhood data
    const fetchNeighborhood = useCallback(async (conceptLabel: string | null): Promise<GraphNeighborhood | null> => {
        const cacheKey = conceptLabel || '__root__';
        
        // Check cache first
        if (graphDataCache.current.has(cacheKey)) {
            return graphDataCache.current.get(cacheKey)!;
        }

        try {
            setLoading(true);
            const data = await graphApi.getNeighborhood(conceptLabel || undefined);
            if (data) {
                graphDataCache.current.set(cacheKey, data);
            }
            return data;
        } catch (err) {
            console.error("Failed to fetch neighborhood:", err);
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    // Handle node click - drill down into the graph
    const handleNodeClick = useCallback(async (nodeId: string, nodeName: string) => {
        // Skip if it's a placeholder or the root node
        if (nodeId === 'empty_placeholder' || nodeId.startsWith('synaptiq:root:')) {
            return;
        }

        console.log("Node clicked:", nodeName);

        // Add current center to navigation stack for back navigation
        if (currentCenter !== null || navigationStack.length === 0) {
            setNavigationStack(prev => [...prev, currentCenter || '__root__']);
        }

        // Fetch the clicked node's neighborhood
        const data = await fetchNeighborhood(nodeName);
        
        if (data && htRef.current) {
            const jitJson = transformToJITFormat(data, null);
            console.log("Loading neighborhood for:", nodeName, jitJson);
            
            htRef.current.loadJSON(jitJson);
            htRef.current.refresh();
            htRef.current.controller.onComplete();
            
            setCurrentCenter(nodeName);
        }

        // Notify parent if callback provided
        if (onNodeClick) {
            onNodeClick(nodeId, nodeName);
        }
    }, [currentCenter, navigationStack, fetchNeighborhood, onNodeClick]);

    // Go back to previous view
    const handleGoBack = useCallback(async () => {
        if (navigationStack.length === 0) return;

        const previousCenter = navigationStack[navigationStack.length - 1];
        setNavigationStack(prev => prev.slice(0, -1));

        const conceptLabel = previousCenter === '__root__' ? null : previousCenter;
        const data = await fetchNeighborhood(conceptLabel);

        if (data && htRef.current) {
            const jitJson = transformToJITFormat(data, null);
            htRef.current.loadJSON(jitJson);
            htRef.current.refresh();
            htRef.current.controller.onComplete();
            
            setCurrentCenter(conceptLabel);
        }
    }, [navigationStack, fetchNeighborhood]);

    // Initialize Hypertree
    useEffect(() => {
        if (!jitLoaded || !document.getElementById(containerId.current)) return;

        const initHypertree = async () => {
            const infovis = document.getElementById(containerId.current);
            if (!infovis) return;

            const w = infovis.offsetWidth - 50;
            const h = infovis.offsetHeight - 50;

            // Create Hypertree instance
            const ht = new window.$jit.Hypertree({
                injectInto: containerId.current,
                width: w,
                height: h,
                Node: {
                    dim: 16,
                    color: "#6366F1",
                    overridable: true,
                    type: 'circle'
                },
                Edge: {
                    lineWidth: 2,
                    color: "#F59E0B",
                    overridable: true
                },
                onBeforeCompute: function (node: any) {
                    // Called before centering on a node
                },
                onCreateLabel: function (domElement: HTMLElement, node: any) {
                    domElement.innerHTML = node.name;
                    domElement.style.cursor = "pointer";
                    
                    // Double-click to drill down
                    domElement.ondblclick = function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        handleNodeClick(node.id, node.name);
                    };
                    
                    // Single click just centers
                    domElement.onclick = function () {
                        ht.onClick(node.id, {
                            onComplete: function () {
                                ht.controller.onComplete();
                            }
                        });
                    };
                },
                onPlaceLabel: function (domElement: HTMLElement, node: any) {
                    const style = domElement.style;
                    style.display = "";
                    style.cursor = "pointer";
                    style.color = "#FFFFFF";
                    style.fontFamily = "SF Pro Display, Inter, sans-serif";
                    style.fontSize = "12px";
                    style.fontWeight = "500";
                    style.pointerEvents = "auto";
                    style.textShadow = "0 1px 2px rgba(0,0,0,0.8)";

                    if (node._depth <= 1) {
                        style.position = 'absolute';
                        const left = parseInt(style.left);
                        const width = domElement.offsetWidth;
                        style.left = (left - width / 2) + 'px';
                    } else if (node._depth === 2) {
                        style.fontSize = "10px";
                        style.opacity = "0.7";
                    } else {
                        style.display = "none";
                    }
                },
                onComplete: function () {
                    // Animation complete
                }
            });

            htRef.current = ht;

            // Load initial data
            const data = await fetchNeighborhood(currentCenter);
            
            if (data) {
                const jitJson = transformToJITFormat(data, null);
                console.log("Initial graph data:", jitJson);
                
                ht.loadJSON(jitJson);
                ht.refresh();
                ht.controller.onComplete();
            } else {
                // Load empty state
                const emptyState = {
                    id: 'empty',
                    name: 'No Data',
                    data: { $color: '#4B5563', $dim: 20 },
                    children: [{
                        id: 'hint',
                        name: 'Ingest content to build your graph',
                        data: { $color: '#6B7280', $dim: 10 },
                        children: []
                    }]
                };
                ht.loadJSON(emptyState);
                ht.refresh();
            }
        };

        initHypertree();

        // Cleanup
        return () => {
            if (htRef.current) {
                // Clear the container
                const container = document.getElementById(containerId.current);
                if (container) {
                    container.innerHTML = '';
                }
                htRef.current = null;
            }
        };
    }, [jitLoaded, fetchNeighborhood, currentCenter, handleNodeClick]);

    return (
        <div className={`relative w-full h-full bg-[#1C1C1E] overflow-hidden ${className || ''}`}>
            {/* Background Gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-black/50 to-transparent pointer-events-none" />

            {/* Navigation Controls */}
            <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
                {navigationStack.length > 0 && (
                    <button
                        onClick={handleGoBack}
                        className="bg-white/10 backdrop-blur-md text-white/90 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/10 hover:bg-white/20 transition-colors flex items-center gap-1"
                    >
                        ← Back
                    </button>
                )}
                {currentCenter && (
                    <span className="text-white/60 text-xs bg-black/30 px-2 py-1 rounded">
                        Viewing: {currentCenter}
                    </span>
                )}
            </div>

            {/* Instructions */}
            <div className="absolute bottom-4 left-4 z-20 text-white/40 text-xs">
                <span>Click to center • Double-click to explore</span>
            </div>

            {/* Canvas Container */}
            <div 
                id={containerId.current} 
                className="w-full h-full flex justify-center items-center" 
                style={{ margin: '0 auto', position: 'relative' }} 
            />

            {/* Loading State */}
            {(!jitLoaded || loading) && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-30">
                    <div className="text-white/80 flex items-center gap-2">
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        {!jitLoaded ? 'Loading Graph Engine...' : 'Loading...'}
                    </div>
                </div>
            )}
        </div>
    );
}
