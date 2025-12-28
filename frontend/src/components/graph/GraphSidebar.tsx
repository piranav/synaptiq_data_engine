"use client";

import { ChevronRight, ChevronDown, BookOpen, Link as LinkIcon, Layers, X } from "lucide-react";
import { useState, useEffect } from "react";

// Convert text to Pascal Case
function toPascalCase(str: string): string {
    return str
        .split(/[\s_-]+/)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

export interface NodeInfo {
    id: string;
    name: string;
    relation?: string;
    parentName?: string;   // Which parent this connection came from
    children?: NodeInfo[];
    definition?: string;
    source?: {
        title?: string;
        url?: string;
    };
    metadata?: Record<string, any>;
}

interface GraphSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    centeredNode: NodeInfo | null;
    adjacentNodes: NodeInfo[];
    onNodeSelect: (nodeId: string, nodeName: string) => void;
}

export function GraphSidebar({
    isOpen,
    onClose,
    centeredNode,
    adjacentNodes,
    onNodeSelect
}: GraphSidebarProps) {
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

    // Reset expanded nodes when centered node changes
    useEffect(() => {
        setExpandedNodes(new Set());
    }, [centeredNode?.id]);

    const toggleNode = (nodeId: string) => {
        setExpandedNodes(prev => {
            const next = new Set(prev);
            if (next.has(nodeId)) {
                next.delete(nodeId);
            } else {
                next.add(nodeId);
            }
            return next;
        });
    };

    if (!isOpen) return null;

    const displayName = centeredNode ? toPascalCase(centeredNode.name) : "Graph Explorer";

    return (
        <div className="fixed right-0 top-0 h-full w-80 bg-[#1C1C1E]/95 backdrop-blur-xl border-l border-white/10 z-30 flex flex-col shadow-2xl transition-transform duration-300">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
                <h2 className="text-lg font-semibold text-white">
                    {displayName}
                </h2>
                <button
                    onClick={onClose}
                    className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/60 hover:text-white"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {/* Content - hidden scrollbar */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 no-scrollbar">
                {/* Centered Node Info */}
                {centeredNode && !centeredNode.name.toLowerCase().includes("knowledge") && (
                    <div className="bg-[#2C2C2E] rounded-xl p-4 border border-white/5">
                        <h3 className="text-sm font-medium text-white/60 mb-2">Current Focus</h3>
                        <p className="text-lg font-semibold text-white">{toPascalCase(centeredNode.name)}</p>

                        {centeredNode.definition && (
                            <div className="mt-3 flex items-start gap-2">
                                <BookOpen className="w-4 h-4 text-white/40 mt-0.5 flex-shrink-0" />
                                <p className="text-sm text-white/70 leading-relaxed">
                                    {centeredNode.definition}
                                </p>
                            </div>
                        )}

                        {centeredNode.source?.title && (
                            <div className="mt-3 flex items-start gap-2">
                                <LinkIcon className="w-4 h-4 text-white/40 mt-0.5 flex-shrink-0" />
                                <a
                                    href={centeredNode.source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
                                >
                                    {centeredNode.source.title}
                                </a>
                            </div>
                        )}
                    </div>
                )}

                {/* Connections - show each separately */}
                <div className="space-y-2">
                    <h3 className="text-sm font-medium text-white/60 flex items-center gap-2">
                        <Layers className="w-4 h-4" />
                        Connections ({adjacentNodes.length})
                    </h3>

                    {adjacentNodes.length === 0 ? (
                        <p className="text-sm text-white/40 italic">
                            Click on a node to explore its connections
                        </p>
                    ) : (
                        <div className="space-y-1">
                            {adjacentNodes.map((node, index) => (
                                <div
                                    key={`${node.id}-${index}`}
                                    className="flex items-center gap-2 px-3 py-2.5 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                                    onClick={() => onNodeSelect(node.id, node.name)}
                                >
                                    <div className="w-5" /> {/* Spacer for alignment */}
                                    <div className="flex-1 min-w-0">
                                        <span className="text-sm text-white truncate block">
                                            {toPascalCase(node.name)}
                                        </span>
                                        {node.relation && (
                                            <span className="text-xs text-white/40 block">
                                                {node.relation}
                                                {node.parentName && node.parentName !== centeredNode?.name && (
                                                    <span className="text-white/30"> via {toPascalCase(node.parentName)}</span>
                                                )}
                                            </span>
                                        )}
                                        {node.source?.title && (
                                            <span className="text-xs text-blue-400/60 block truncate">
                                                from {node.source.title}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Footer hint */}
            <div className="p-4 border-t border-white/10">
                <p className="text-xs text-white/40 text-center">
                    Click a connection to navigate
                </p>
            </div>
        </div>
    );
}
