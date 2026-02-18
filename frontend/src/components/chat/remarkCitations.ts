import type { Plugin } from "unified";
import type { Root } from "mdast";

type MdastNode = {
    type: string;
    value?: string;
    children?: MdastNode[];
    [key: string]: unknown;
};

interface CitationPluginOptions {
    prefix?: string;
}

function citationId(index: number, prefix?: string) {
    return prefix ? `${prefix}-citation-${index}` : `citation-${index}`;
}

function transformTextNode(value: string, prefix?: string): MdastNode[] {
    const nodes: MdastNode[] = [];
    const regex = /\[(\d+)\]/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null = regex.exec(value);

    while (match) {
        if (match.index > lastIndex) {
            nodes.push({
                type: "text",
                value: value.slice(lastIndex, match.index),
            });
        }

        const citationIndex = Number.parseInt(match[1], 10);
        nodes.push({
            type: "link",
            url: `#${citationId(citationIndex, prefix)}`,
            title: `Source ${citationIndex}`,
            data: {
                hProperties: {
                    className: ["citation-ref"],
                },
            },
            children: [
                {
                    type: "text",
                    value: `[${citationIndex}]`,
                },
            ],
        });

        lastIndex = regex.lastIndex;
        match = regex.exec(value);
    }

    if (lastIndex < value.length) {
        nodes.push({
            type: "text",
            value: value.slice(lastIndex),
        });
    }

    return nodes;
}

function walk(node: MdastNode, prefix?: string): void {
    if (!node.children || node.children.length === 0) {
        return;
    }

    const nextChildren: MdastNode[] = [];
    for (const child of node.children) {
        if (child.type === "text" && typeof child.value === "string" && /\[\d+\]/.test(child.value)) {
            nextChildren.push(...transformTextNode(child.value, prefix));
            continue;
        }
        walk(child, prefix);
        nextChildren.push(child);
    }
    node.children = nextChildren;
}

export const remarkCitations: Plugin<[CitationPluginOptions?], Root> = (options) => {
    const prefix = options?.prefix;
    return (tree) => {
        walk(tree as MdastNode, prefix);
    };
};
