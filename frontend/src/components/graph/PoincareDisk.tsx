"use client";

import { useEffect, useRef, useState, useId, useCallback } from "react";
import { graphApi, GraphNeighborhood } from "@/lib/api/graph";
import { transformToJITFormat, SWISS_COLORS } from "@/lib/graph/adapter";
import { NodeInfo } from "@/components/graph/GraphSidebar";

// We need to tell TS about $jit on window if we import it
declare global {
    interface Window {
        $jit: any;
    }
}

interface PoincareDiskProps {
    centerNode?: string | null;
    userName?: string;  // For root node name
    onNodeClick?: (nodeId: string, nodeLabel: string) => void;
    onCenterChange?: (centeredNode: NodeInfo | null, adjacentNodes: NodeInfo[]) => void;
    onHypertreeReady?: (navigateToNode: (nodeId: string) => void) => void;  // Expose navigation
    className?: string;
    isPreview?: boolean;
}

export function PoincareDisk({ centerNode: initialCenterNode, userName, onNodeClick, onCenterChange, onHypertreeReady, className, isPreview = false }: PoincareDiskProps) {
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

    // Fetch neighborhood data for a specific concept (not root)
    const fetchNeighborhood = useCallback(async (conceptLabel: string): Promise<GraphNeighborhood | null> => {
        const cacheKey = conceptLabel;

        // Check cache first
        if (graphDataCache.current.has(cacheKey)) {
            return graphDataCache.current.get(cacheKey)!;
        }

        try {
            setLoading(true);
            const data = await graphApi.getNeighborhood(conceptLabel);
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

        if (previousCenter === '__root__') {
            // Go back to root - reload the JIT tree
            try {
                const jitTree = await graphApi.getJITTree();
                if (jitTree && htRef.current) {
                    htRef.current.loadJSON(jitTree);
                    htRef.current.refresh();
                    htRef.current.controller.onComplete();
                }
            } catch (err) {
                console.error("Failed to reload root tree:", err);
            }
            setCurrentCenter(null);
        } else {
            // Go back to a specific concept
            const data = await fetchNeighborhood(previousCenter);
            if (data && htRef.current) {
                const jitJson = transformToJITFormat(data, null);
                htRef.current.loadJSON(jitJson);
                htRef.current.refresh();
                htRef.current.controller.onComplete();
                setCurrentCenter(previousCenter);
            }
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

            // Create Hypertree instance with Swiss design styling
            const ht = new window.$jit.Hypertree({
                injectInto: containerId.current,
                width: w,
                height: h,
                Node: {
                    dim: 14,
                    color: SWISS_COLORS.concept,
                    overridable: true,
                    type: 'circle'
                },
                Edge: {
                    lineWidth: 1.5,
                    color: "#555555",  // Muted gray for Swiss style
                    overridable: true
                },
                onBeforeCompute: function (node: any) {
                    // Called before centering on a node
                },
                onCreateLabel: function (domElement: HTMLElement, node: any) {
                    // Convert text to Pascal Case
                    const toPascalCase = (str: string): string => {
                        return str
                            .split(/[\s_-]+/)
                            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                            .join(' ');
                    };

                    // Build label with relationship type if available
                    const relLabel = node.data?.relationLabel;
                    const isClickable = node.id !== 'empty_placeholder' && !node.id.startsWith('synaptiq:root:');
                    const displayName = toPascalCase(node.name);

                    let labelHtml = '';
                    if (relLabel && node._depth > 0) {
                        labelHtml = `<span class="node-label">${displayName}</span><span class="rel-type">${relLabel}</span>`;
                    } else {
                        labelHtml = displayName;
                    }

                    // Add visual drill hint for child nodes
                    if (isClickable && node._depth > 0) {
                        labelHtml += `<span class="drill-hint">▸</span>`;
                    }

                    domElement.innerHTML = labelHtml;
                    domElement.style.cursor = isClickable ? "pointer" : "default";

                    // Single click: Animate to center on this node (hyperbolic animation)
                    // The multi-level tree is preserved - no data replacement
                    domElement.onclick = function (e) {
                        e.preventDefault();
                        e.stopPropagation();

                        // Animate to center on this node - tree structure stays intact
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
                    style.fontFamily = "'SF Pro Display', 'Inter', -apple-system, sans-serif";
                    style.fontSize = "12px";
                    style.fontWeight = "500";
                    style.letterSpacing = "-0.01em";
                    style.pointerEvents = "auto";
                    style.textShadow = "0 1px 3px rgba(0,0,0,0.9)";

                    // Style the relationship type label
                    const relTypeEl = domElement.querySelector('.rel-type') as HTMLElement;
                    if (relTypeEl) {
                        relTypeEl.style.display = 'block';
                        relTypeEl.style.fontSize = '9px';
                        relTypeEl.style.fontWeight = '400';
                        relTypeEl.style.color = 'rgba(255,255,255,0.5)';
                        relTypeEl.style.marginTop = '2px';
                    }

                    // Style the drill hint arrow
                    const drillHint = domElement.querySelector('.drill-hint') as HTMLElement;
                    if (drillHint) {
                        drillHint.style.display = 'inline';
                        drillHint.style.marginLeft = '4px';
                        drillHint.style.fontSize = '10px';
                        drillHint.style.color = 'rgba(10, 132, 255, 0.8)';
                    }

                    if (node._depth <= 1) {
                        style.position = 'absolute';
                        const left = parseInt(style.left);
                        const width = domElement.offsetWidth;
                        style.left = (left - width / 2) + 'px';
                        style.fontWeight = '600';
                    } else if (node._depth === 2) {
                        style.fontSize = "10px";
                        style.opacity = "0.8";
                    } else {
                        style.display = "none";
                    }
                },
                onComplete: function () {
                    // Build adjacent nodes for sidebar
                    if (onCenterChange && !isPreview) {
                        const centeredNode = ht.graph.getClosestNodeToOrigin("current");
                        if (centeredNode) {
                            const adjacentNodes: NodeInfo[] = [];
                            centeredNode.eachAdjacency(function (adj: any) {
                                const child = adj.nodeTo;
                                const parent = adj.nodeFrom;
                                if (child && child.name) {
                                    const childData = child.data || {};
                                    adjacentNodes.push({
                                        id: child.id,
                                        name: child.name,
                                        relation: childData.relation || childData.relationLabel,
                                        parentName: parent?.name,  // Track which node this connection came from
                                        definition: childData.definition,
                                        source: childData.sourceTitle ? { title: childData.sourceTitle } : undefined,
                                    });
                                }
                            });
                            const centeredData = centeredNode.data || {};
                            onCenterChange(
                                {
                                    id: centeredNode.id,
                                    name: centeredNode.name,
                                    relation: centeredData.relation,
                                    definition: centeredData.definition,
                                    source: centeredData.sourceTitle ? { title: centeredData.sourceTitle } : undefined,
                                },
                                adjacentNodes
                            );
                        }
                    }
                },
                // Enable zoom with mouse wheel
                Navigation: {
                    enable: true,
                    panning: true,  // Enable drag to pan
                    zooming: 20     // Zoom step size
                }
            });

            htRef.current = ht;

            // Expose navigation function to parent
            if (onHypertreeReady) {
                onHypertreeReady((nodeId: string) => {
                    if (ht && ht.graph.getNode(nodeId)) {
                        ht.onClick(nodeId, {
                            onComplete: function () {
                                ht.controller.onComplete();
                            }
                        });
                    }
                });
            }

            // Load initial data - backend now returns JIT-compatible tree structure directly
            try {
                setLoading(true);
                // Fetch the JIT-compatible tree directly
                const jitTree = await graphApi.getJITTree();
                console.log("JIT Tree loaded:", jitTree);

                if (jitTree && jitTree.id && jitTree.children) {
                    // Replace root node name with user's name if provided
                    if (userName && jitTree.name === "Knowledge Graph") {
                        jitTree.name = `${userName}'s Knowledge`;
                    }

                    // Tree is already in JIT format, load directly
                    ht.loadJSON(jitTree);

                    // Apply cross-node adjacencies if present
                    // This connects siblings/cousins that represent the same concept
                    if (jitTree.adjacencies && Array.isArray(jitTree.adjacencies)) {
                        console.log(`Applying ${jitTree.adjacencies.length} cross-node adjacencies`);
                        for (const adj of jitTree.adjacencies) {
                            try {
                                ht.graph.addAdjacence(
                                    { id: adj.nodeFrom },
                                    { id: adj.nodeTo },
                                    adj.data || {}
                                );
                            } catch (e) {
                                // Node might not exist, skip
                                console.debug(`Skipped adjacency ${adj.nodeFrom} -> ${adj.nodeTo}`);
                            }
                        }
                    }

                    ht.refresh();
                    ht.controller.onComplete();
                } else {
                    // Fallback: try old format with transformation (only for specific concepts)
                    if (currentCenter) {
                        const data = await fetchNeighborhood(currentCenter);
                        if (data && 'found' in data) {
                            const jitJson = transformToJITFormat(data as any, null);
                            ht.loadJSON(jitJson);
                            ht.refresh();
                            ht.controller.onComplete();
                        }
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
                }
            } catch (err) {
                console.error("Failed to load graph data:", err);
                const emptyState = {
                    id: 'empty',
                    name: 'Error loading graph',
                    data: { $color: '#EF4444', $dim: 20 },
                    children: []
                };
                ht.loadJSON(emptyState);
                ht.refresh();
            } finally {
                setLoading(false);
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
