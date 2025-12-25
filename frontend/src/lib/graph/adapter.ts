import { GraphNeighborhood, RelationshipTarget } from "@/lib/api/graph";

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
        relationLabel?: string;
        definition?: string;
        nodeType?: string;
        entityType?: string;
        sourceType?: string;
        [key: string]: any;
    };
    children: JITTreeNode[];
}

/**
 * Swiss Design Color Palette
 * Clean, semantic colors with high contrast and minimal distraction.
 * Inspired by Swiss/International Typographic Style.
 */
const SWISS_COLORS = {
    // Node Entity Types
    root: '#1A1A1A',           // Near-black for root
    concept: '#0066CC',        // Primary blue for concepts
    definition: '#CC3300',     // Accent red for definitions
    source: '#339966',         // Green for sources
    chunk: '#666666',          // Gray for chunks

    // Source Type Variants
    youtube: '#FF0000',        // YouTube red
    web_article: '#4285F4',    // Google blue
    note: '#FFC107',           // Amber/yellow for notes
    pdf: '#FF5722',            // Deep orange for PDFs
    podcast: '#9C27B0',        // Purple for podcasts

    // Relationship Types (for future edge coloring)
    isA: '#4A4A4A',            // Hierarchy - dark gray
    partOf: '#0052A3',         // Composition - dark blue
    prerequisiteFor: '#CC7700', // Learning path - orange
    relatedTo: '#888888',      // Association - medium gray
    oppositeOf: '#CC0033',     // Contrast - red
    usedIn: '#339966',         // Usage - green
};

/**
 * Human-readable labels for relationship types
 */
const RELATIONSHIP_LABELS: Record<string, string> = {
    isA: 'is a',
    partOf: 'part of',
    prerequisiteFor: 'requires',
    relatedTo: 'related to',
    oppositeOf: 'opposite of',
    usedIn: 'used in',
    contains: 'contains',
};

/**
 * Get color for a node based on its entity type and source type
 */
function getNodeColor(entityType?: string, sourceType?: string): string {
    if (sourceType) {
        const sourceColor = SWISS_COLORS[sourceType as keyof typeof SWISS_COLORS];
        if (sourceColor) return sourceColor;
    }

    switch (entityType) {
        case 'concept':
            return SWISS_COLORS.concept;
        case 'definition':
            return SWISS_COLORS.definition;
        case 'source':
            return SWISS_COLORS.source;
        case 'chunk':
            return SWISS_COLORS.chunk;
        default:
            return SWISS_COLORS.concept;
    }
}

/**
 * Get node size based on type and depth
 * Classes and root nodes are larger; instances are smaller
 */
function getNodeSize(nodeType?: string, isRoot: boolean = false): number {
    if (isRoot) return 28;
    if (nodeType === 'class') return 20;
    return 14;
}

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
    // Create root node with Swiss design styling
    const rootId = centerNode.uri || 'root';
    const rootColor = getNodeColor(centerNode.entityType, centerNode.sourceType);

    const rootNode: JITTreeNode = {
        id: rootId,
        name: centerNode.label || 'Knowledge Graph',
        data: {
            $color: rootColor,
            $type: 'circle',
            $dim: getNodeSize(centerNode.nodeType, true),
            definition: centerNode.definition,
            nodeType: centerNode.nodeType || 'instance',
            entityType: centerNode.entityType || 'concept',
            sourceType: centerNode.sourceType,
        },
        children: []
    };

    // Process relationships into children
    // Use richRelationships if available for more metadata
    const richRels = centerNode.richRelationships;
    const simpleRels = centerNode.relationships;

    if (richRels && Object.keys(richRels).length > 0) {
        // Use rich relationships with full metadata
        Object.entries(richRels).forEach(([relType, targets]) => {
            if (!targets || targets.length === 0) return;

            targets.forEach((target: any, index: number) => {
                const targetId = `${relType}_${target.label.replace(/\s+/g, '_')}_${index}`;
                const targetColor = getNodeColor(target.entityType);
                const targetRelation = target.relation || relType;

                // Build grandchildren from nested children (2nd level)
                const grandchildren: JITTreeNode[] = [];
                if (target.children && Array.isArray(target.children)) {
                    target.children.forEach((grandchild: any, gIndex: number) => {
                        const gcId = `${targetId}_${grandchild.label.replace(/\s+/g, '_')}_${gIndex}`;
                        const gcRelation = grandchild.relation || 'relatedTo';

                        grandchildren.push({
                            id: gcId,
                            name: grandchild.label,
                            data: {
                                $color: getNodeColor(grandchild.entityType),
                                $type: 'circle',
                                $dim: 10,
                                relation: gcRelation,
                                relationLabel: RELATIONSHIP_LABELS[gcRelation] || gcRelation,
                                nodeType: grandchild.nodeType || 'instance',
                                entityType: grandchild.entityType || 'concept',
                            },
                            children: []  // Could go deeper if needed
                        });
                    });
                }

                const childNode: JITTreeNode = {
                    id: targetId,
                    name: target.label,
                    data: {
                        $color: targetColor,
                        $type: 'circle',
                        $dim: getNodeSize(target.nodeType),
                        relation: targetRelation,
                        relationLabel: RELATIONSHIP_LABELS[targetRelation] || targetRelation,
                        nodeType: target.nodeType,
                        entityType: target.entityType,
                    },
                    children: grandchildren  // Nested children for 2nd level!
                };

                rootNode.children.push(childNode);
            });
        });
    } else if (simpleRels) {
        // Fallback to simple relationships (just labels)
        Object.entries(simpleRels).forEach(([relType, targets]) => {
            if (!targets || targets.length === 0) return;

            targets.forEach((targetLabel, index) => {
                const targetId = `${relType}_${targetLabel.replace(/\s+/g, '_')}_${index}`;

                const childNode: JITTreeNode = {
                    id: targetId,
                    name: targetLabel,
                    data: {
                        $color: SWISS_COLORS.concept,
                        $type: 'circle',
                        $dim: 14,
                        relation: relType,
                        relationLabel: RELATIONSHIP_LABELS[relType] || relType,
                        nodeType: 'instance',
                        entityType: 'concept',
                    },
                    children: []
                };

                rootNode.children.push(childNode);
            });
        });
    }

    // If no children were added, show a placeholder
    if (rootNode.children.length === 0) {
        rootNode.children.push({
            id: 'empty_placeholder',
            name: 'No connections yet',
            data: {
                $color: '#4B5563',
                $dim: 8,
                nodeType: 'instance',
                entityType: 'concept',
            },
            children: []
        });
    }

    return rootNode;
}

/**
 * Export color palette for use in other components (legend, etc.)
 */
export { SWISS_COLORS, RELATIONSHIP_LABELS };
