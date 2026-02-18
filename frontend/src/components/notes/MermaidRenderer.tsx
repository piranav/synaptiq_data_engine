"use client";

import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

interface MermaidRendererProps {
    code: string;
    className?: string;
    theme?: "light" | "dark";
}

function getThemeConfig(theme: "light" | "dark") {
    if (theme === "light") {
        return {
            theme: "default" as const,
            themeVariables: {
                primaryColor: "#256BEE",
                primaryTextColor: "#0f172a",
                primaryBorderColor: "#256BEE",
                lineColor: "#256BEE",
                secondaryColor: "#f6f8fb",
                tertiaryColor: "#ffffff",
                background: "#ffffff",
                mainBkg: "#f6f8fb",
                nodeBorder: "#256BEE",
                clusterBkg: "#f6f8fb",
                clusterBorder: "#d2d8e1",
                titleColor: "#0f172a",
                edgeLabelBackground: "#ffffff",
            },
        };
    }

    return {
        theme: "dark" as const,
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
    };
}

export function MermaidRenderer({ code, className = "", theme = "dark" }: MermaidRendererProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);
    const [svg, setSvg] = useState<string>("");

    useEffect(() => {
        const renderDiagram = async () => {
            if (!code.trim() || !containerRef.current) return;

            try {
                setError(null);
                const id = `mermaid-${Date.now()}`;
                const config = getThemeConfig(theme);

                mermaid.initialize({
                    startOnLoad: false,
                    theme: config.theme,
                    themeVariables: config.themeVariables,
                    flowchart: {
                        htmlLabels: true,
                        curve: "basis",
                    },
                });

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
    }, [code, theme]);

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
