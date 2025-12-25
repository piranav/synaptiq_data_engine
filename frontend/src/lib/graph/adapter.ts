import { GraphNeighborhood } from "@/lib/api/graph";

/**
 * JIT Hypertree Node structure
 * Hypertree requires a TREE structure with a single root node and nested children.
 */
interface JITTreeNode {
    id: string;
    name: string;
    data: {
        $color?: string;
        $type?: string;
        $dim?: number;
        relation?: string;
        definition?: string;
        [key: string]: any;
    };
    children: JITTreeNode[];
}

const COLORS = {
    root: '#8B5CF6',       // Purple for root
    concept: '#6366F1',    // Indigo for concepts
    definition: '#EC4899', // Pink
    source: '#14B8A6',     // Teal
    edge: '#F59E0B',       // Amber
};

/**
 * Transform GraphNeighborhood to JIT Hypertree format.
 * 
 * JIT Hypertree expects a TREE structure:
 * {
 *   id: "root",
 *   name: "Root Label",
 *   data: { ... },
 *   children: [
 *     { id: "child1", name: "Child 1", data: {...}, children: [] },
 *     ...
 *   ]
 * }
 */
export function transformToJITFormat(
    centerNode: GraphNeighborhood,
    neighborhood: any
): JITTreeNode {
    // Create root node
    const rootId = centerNode.uri || 'root';
    const rootNode: JITTreeNode = {
        id: rootId,
        name: centerNode.label || 'Knowledge Graph',
        data: {
            $color: COLORS.root,
            $type: 'circle',
            $dim: 25,
            definition: centerNode.definition,
        },
        children: []
    };

    // Process relationships into children
    // Group by relationship type for better organization
    if (centerNode.relationships) {
        Object.entries(centerNode.relationships).forEach(([relType, targets]) => {
            if (!targets || targets.length === 0) return;

            // For each relationship type, create children nodes
            targets.forEach((targetLabel, index) => {
                // Generate unique ID from label
                const targetId = `${relType}_${targetLabel.replace(/\s+/g, '_')}_${index}`;

                const childNode: JITTreeNode = {
                    id: targetId,
                    name: targetLabel,
                    data: {
                        $color: COLORS.concept,
                        $type: 'circle',
                        $dim: 12,
                        relation: relType,
                    },
                    children: [] // Leaf nodes have no children
                };

                rootNode.children.push(childNode);
            });
        });
    }

    // If no children were added, show a placeholder
    if (rootNode.children.length === 0) {
        rootNode.children.push({
            id: 'empty_placeholder',
            name: 'No concepts yet',
            data: {
                $color: '#4B5563', // Gray
                $dim: 8,
            },
            children: []
        });
    }

    return rootNode;
}
