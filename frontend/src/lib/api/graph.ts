import { api } from "./client";

export interface GraphStats {
    totalConcepts: number;
    totalSources: number;
    relationships: Record<string, number>;
}

export interface GraphNeighborhood {
    found: boolean;
    uri: string;
    label: string;
    definition?: string;
    source?: {
        title?: string;
        url?: string;
    };
    relationships: Record<string, string[]>;
}

export const graphApi = {
    getStats: async (): Promise<GraphStats> => {
        const response = await api.get("/graph/stats");
        return response.data;
    },

    getNeighborhood: async (nodeLabel?: string): Promise<GraphNeighborhood> => {
        let url = "/graph/neighborhood";
        if (nodeLabel) {
            url += `?concept_label=${encodeURIComponent(nodeLabel)}`;
        }
        const response = await api.get(url);
        return response.data;
    }
};
