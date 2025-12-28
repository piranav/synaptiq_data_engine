import { api } from "./client";

export interface GraphStats {
    totalConcepts: number;
    totalSources: number;
    relationships: Record<string, number>;
}

export interface RelationshipTarget {
    uri: string;
    label: string;
    nodeType: 'class' | 'instance';
    entityType: 'concept' | 'definition' | 'source';
}

export interface GraphNeighborhood {
    found: boolean;
    uri: string;
    label: string;
    nodeType: 'class' | 'instance';
    entityType: 'concept' | 'definition' | 'source';
    sourceType?: 'youtube' | 'web_article' | 'note' | 'pdf';
    definition?: string;
    source?: {
        title?: string;
        url?: string;
    };
    relationships: Record<string, string[]>;
    richRelationships?: Record<string, RelationshipTarget[]>;
}

// JIT Hypertree compatible node structure
export interface JITAdjacency {
    nodeFrom: string;
    nodeTo: string;
    data?: {
        $color?: string;
        $lineWidth?: number;
        [key: string]: any;
    };
}

export interface JITTreeNode {
    id: string;
    name: string;
    data: {
        relation?: string;
        $color?: string;
        $dim?: number;
        [key: string]: any;
    };
    children: JITTreeNode[];
    adjacencies?: JITAdjacency[];  // Cross-node connections
}

export const graphApi = {
    getStats: async (): Promise<GraphStats> => {
        const response = await api.get("/graph/stats");
        return response.data;
    },

    getNeighborhood: async (nodeLabel: string): Promise<GraphNeighborhood> => {
        const url = `/graph/neighborhood?concept_label=${encodeURIComponent(nodeLabel)}`;
        const response = await api.get(url);
        return response.data;
    },

    // New: Get JIT-compatible tree directly for root view
    getJITTree: async (): Promise<JITTreeNode> => {
        const response = await api.get("/graph/neighborhood");
        return response.data;
    }
};
