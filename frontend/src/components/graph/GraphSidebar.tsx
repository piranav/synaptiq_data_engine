"use client";

import { BookOpen, Link as LinkIcon, Layers, X } from "lucide-react";
import { useEffect } from "react";

function toPascalCase(str: string): string {
  return str
    .split(/[\s_-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export interface NodeInfo {
  id: string;
  name: string;
  relation?: string;
  parentName?: string;
  children?: NodeInfo[];
  definition?: string;
  source?: {
    title?: string;
    url?: string;
  };
  metadata?: Record<string, unknown>;
}

interface GraphSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  centeredNode: NodeInfo | null;
  adjacentNodes: NodeInfo[];
  onNodeSelect: (nodeId: string, nodeName: string) => void;
}

export function GraphSidebar({ isOpen, onClose, centeredNode, adjacentNodes, onNodeSelect }: GraphSidebarProps) {
  useEffect(() => {
    // Reserved for future expanded node memory by center node.
  }, [centeredNode?.id]);

  if (!isOpen) return null;

  const displayName = centeredNode ? toPascalCase(centeredNode.name) : "Graph Explorer";

  return (
    <div className="fixed right-0 top-0 h-full w-80 glass-sidebar border-l border-border z-30 flex flex-col shadow-elevated transition-transform duration-300">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold text-primary">{displayName}</h2>
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-[var(--hover-bg)] transition-colors text-secondary hover:text-primary">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 thin-scrollbar">
        {centeredNode && !centeredNode.name.toLowerCase().includes("knowledge") && (
          <div className="dashboard-card rounded-xl p-4">
            <h3 className="text-sm font-medium text-secondary mb-2">Current Focus</h3>
            <p className="text-lg font-semibold text-primary">{toPascalCase(centeredNode.name)}</p>

            {centeredNode.definition && (
              <div className="mt-3 flex items-start gap-2">
                <BookOpen className="w-4 h-4 text-secondary mt-0.5 flex-shrink-0" />
                <p className="text-sm text-secondary leading-relaxed">{centeredNode.definition}</p>
              </div>
            )}

            {centeredNode.source?.title && (
              <div className="mt-3 flex items-start gap-2">
                <LinkIcon className="w-4 h-4 text-secondary mt-0.5 flex-shrink-0" />
                <a
                  href={centeredNode.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-[var(--accent)] hover:underline"
                >
                  {centeredNode.source.title}
                </a>
              </div>
            )}
          </div>
        )}

        <div className="space-y-2">
          <h3 className="text-sm font-medium text-secondary flex items-center gap-2">
            <Layers className="w-4 h-4" />
            Connections ({adjacentNodes.length})
          </h3>

          {adjacentNodes.length === 0 ? (
            <p className="text-sm text-tertiary italic">Click on a node to explore its connections</p>
          ) : (
            <div className="space-y-1">
              {adjacentNodes.map((node, index) => (
                <div
                  key={`${node.id}-${index}`}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-transparent hover:border-border hover:bg-[var(--hover-bg)] cursor-pointer transition-colors"
                  onClick={() => onNodeSelect(node.id, node.name)}
                >
                  <div className="w-5" />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-primary truncate block">{toPascalCase(node.name)}</span>
                    {node.relation && (
                      <span className="text-xs text-secondary block">
                        {node.relation}
                        {node.parentName && node.parentName !== centeredNode?.name && (
                          <span className="text-tertiary"> via {toPascalCase(node.parentName)}</span>
                        )}
                      </span>
                    )}
                    {node.source?.title && <span className="text-xs text-[var(--accent)]/80 block truncate">from {node.source.title}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-border">
        <p className="text-xs text-tertiary text-center">Click a connection to navigate</p>
      </div>
    </div>
  );
}
