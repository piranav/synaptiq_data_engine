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
    adjacencies?: JITAdjacency[];
}

export interface GraphFilters {
    relTypes?: string[];
    sourceFilter?: string;
    minImportance?: number;
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

    getJITTree: async (filters?: GraphFilters): Promise<JITTreeNode> => {
        const params = new URLSearchParams();
        if (filters?.relTypes && filters.relTypes.length > 0) {
            params.set("rel_types", filters.relTypes.join(","));
        }
        if (filters?.sourceFilter) {
            params.set("source_filter", filters.sourceFilter);
        }
        if (filters?.minImportance !== undefined) {
            params.set("min_importance", String(filters.minImportance));
        }
        const query = params.toString();
        const url = `/graph/neighborhood${query ? `?${query}` : ""}`;
        const response = await api.get(url);
        return response.data;
    }
};
