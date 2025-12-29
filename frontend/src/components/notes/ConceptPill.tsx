"use client";

import { Link2 } from "lucide-react";

interface ConceptPillProps {
    concept: string;
    onClick?: (concept: string) => void;
    className?: string;
}

/**
 * Displays a linked concept as an interactive pill.
 * Clicking navigates to the concept in the graph view.
 */
export function ConceptPill({ concept, onClick, className = "" }: ConceptPillProps) {
    // Generate a color based on the concept name
    const getConceptColor = (name: string): string => {
        const colors = [
            { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-300" },
            { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-300" },
            { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-300" },
            { bg: "bg-amber-500/20", border: "border-amber-500/30", text: "text-amber-300" },
            { bg: "bg-rose-500/20", border: "border-rose-500/30", text: "text-rose-300" },
            { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-300" },
        ];
        const hash = name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
        return colors[hash % colors.length].bg + " " + colors[hash % colors.length].border + " " + colors[hash % colors.length].text;
    };

    const colorClasses = getConceptColor(concept);

    return (
        <button
            onClick={() => onClick?.(concept)}
            className={`
                inline-flex items-center gap-1.5 
                h-6 px-2 rounded-full
                border text-[12px] font-medium
                transition-all hover:scale-105
                ${colorClasses}
                ${className}
            `}
            title={`View "${concept}" in graph`}
        >
            <Link2 className="h-3 w-3" strokeWidth={2} />
            <span>{concept}</span>
        </button>
    );
}

/**
 * Renders a list of concept pills.
 */
export function ConceptPillList({
    concepts,
    onConceptClick,
    className = "",
}: {
    concepts: string[];
    onConceptClick?: (concept: string) => void;
    className?: string;
}) {
    if (concepts.length === 0) return null;

    return (
        <div className={`flex flex-wrap gap-2 ${className}`}>
            {concepts.map((concept) => (
                <ConceptPill key={concept} concept={concept} onClick={onConceptClick} />
            ))}
        </div>
    );
}
