"use client";

import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

// Initialize mermaid with dark theme
mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    themeVariables: {
        primaryColor: "#256BEE",
        primaryTextColor: "#fff",
        primaryBorderColor: "#60a5fa",
        lineColor: "#60a5fa",
        secondaryColor: "#1a1d24",
        tertiaryColor: "#0B0D12",
        background: "#0B0D12",
        mainBkg: "#1a1d24",
        nodeBorder: "#60a5fa",
        clusterBkg: "#1a1d24",
        clusterBorder: "#60a5fa",
        titleColor: "#fff",
        edgeLabelBackground: "#1a1d24",
    },
    flowchart: {
        htmlLabels: true,
        curve: "basis",
    },
});

interface MermaidRendererProps {
    code: string;
    className?: string;
}

export function MermaidRenderer({ code, className = "" }: MermaidRendererProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);
    const [svg, setSvg] = useState<string>("");

    useEffect(() => {
        const renderDiagram = async () => {
            if (!code.trim() || !containerRef.current) return;

            try {
                setError(null);
                const id = `mermaid-${Date.now()}`;

                // Validate the syntax first
                const isValid = await mermaid.parse(code);
                if (!isValid) {
                    setError("Invalid mermaid syntax");
                    return;
                }

                // Render the diagram
                const { svg: renderedSvg } = await mermaid.render(id, code);
                setSvg(renderedSvg);
            } catch (err) {
                console.error("Mermaid render error:", err);
                setError(err instanceof Error ? err.message : "Failed to render diagram");
            }
        };

        renderDiagram();
    }, [code]);

    if (error) {
        return (
            <div className={`rounded-md border border-danger/30 bg-danger/10 p-3 ${className}`}>
                <div className="flex items-center gap-2 text-danger text-[12px]">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Mermaid Error: {error}</span>
                </div>
            </div>
        );
    }

    if (!svg) {
        return (
            <div className={`flex items-center justify-center h-32 ${className}`}>
                <div className="text-white/40 text-[12px]">Rendering diagram...</div>
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            className={`mermaid-container flex items-center justify-center overflow-x-auto ${className}`}
            dangerouslySetInnerHTML={{ __html: svg }}
        />
    );
}
