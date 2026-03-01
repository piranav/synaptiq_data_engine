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
                primaryColor: "#07b85b",
                primaryTextColor: "#1a2433",
                primaryBorderColor: "#07b85b",
                lineColor: "#0aa7c5",
                secondaryColor: "#f4f8fb",
                tertiaryColor: "#ffffff",
                background: "#ffffff",
                mainBkg: "#f4f8fb",
                nodeBorder: "#07b85b",
                clusterBkg: "#f4f8fb",
                clusterBorder: "#b9cfdb",
                titleColor: "#1a2433",
                edgeLabelBackground: "#ffffff",
            },
        };
    }

    return {
        theme: "dark" as const,
        themeVariables: {
            primaryColor: "#6dff9a",
            primaryTextColor: "#fff",
            primaryBorderColor: "#6fe0ff",
            lineColor: "#6fe0ff",
            secondaryColor: "#131c2a",
            tertiaryColor: "#080d14",
            background: "#080d14",
            mainBkg: "#131c2a",
            nodeBorder: "#6fe0ff",
            clusterBkg: "#131c2a",
            clusterBorder: "#6fe0ff",
            titleColor: "#fff",
            edgeLabelBackground: "#131c2a",
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
                <div className="text-secondary text-[12px]">Rendering diagram...</div>
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
