"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import clsx from "clsx";
import "katex/dist/katex.min.css";

import { MermaidRenderer } from "@/components/notes/MermaidRenderer";
import { useTheme } from "@/contexts/ThemeContext";
import { remarkCitations } from "./remarkCitations";

interface MarkdownMessageProps {
    content: string;
    className?: string;
    citationAnchorPrefix?: string;
}

export function MarkdownMessage({ content, className, citationAnchorPrefix }: MarkdownMessageProps) {
    const { resolvedTheme } = useTheme();

    return (
        <div className={clsx("markdown-message text-[13px] leading-[20px] break-words", className)}>
            <ReactMarkdown
                remarkPlugins={[
                    remarkGfm,
                    remarkMath,
                    [remarkCitations, { prefix: citationAnchorPrefix }],
                ]}
                rehypePlugins={[rehypeKatex]}
                components={{
                    h1: ({ children }) => <h1 className="text-lg font-semibold mt-3 mb-2 text-primary">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-semibold mt-3 mb-2 text-primary">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1 text-primary">{children}</h3>,
                    p: ({ children }) => <p className="text-primary/90 leading-6 mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1 marker:text-secondary">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1 marker:text-secondary">{children}</ol>,
                    li: ({ children }) => <li className="text-primary/90">{children}</li>,
                    blockquote: ({ children }) => (
                        <blockquote className="mb-2 border-l-2 border-border pl-3 italic text-secondary">
                            {children}
                        </blockquote>
                    ),
                    hr: () => <hr className="my-3 border-border-subtle" />,
                    a: ({ href, children, className: linkClass }) => {
                        const isCitation = typeof href === "string" && href.includes("-citation-");
                        return (
                            <a
                                href={href}
                                className={clsx(
                                    isCitation
                                        ? "inline-flex items-center px-1.5 py-0.5 rounded border border-border bg-surface text-xs text-secondary hover:text-primary hover:bg-elevated transition-colors"
                                        : "text-accent hover:underline",
                                    linkClass
                                )}
                                target={isCitation ? undefined : "_blank"}
                                rel={isCitation ? undefined : "noopener noreferrer"}
                            >
                                {children}
                            </a>
                        );
                    },
                    table: ({ children }) => (
                        <div className="overflow-x-auto mb-2">
                            <table className="w-full border-collapse border border-border text-[12px]">{children}</table>
                        </div>
                    ),
                    thead: ({ children }) => <thead className="bg-elevated">{children}</thead>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-medium text-primary">{children}</th>,
                    td: ({ children }) => <td className="border border-border px-2 py-1 text-primary/90">{children}</td>,
                    code: ({ className: codeClass, children, ...props }) => {
                        const match = /language-(\w+)/.exec(codeClass || "");
                        const language = match?.[1]?.toLowerCase();
                        const rawCode = String(children).replace(/\n$/, "");

                        if (language === "mermaid") {
                            return (
                                <MermaidRenderer
                                    code={rawCode}
                                    className="my-2 rounded-md border border-border bg-surface p-3"
                                    theme={resolvedTheme}
                                />
                            );
                        }

                        if (language) {
                            return (
                                <pre
                                    className={clsx(
                                        "my-2 overflow-x-auto rounded-md border border-border p-3 bg-canvas/70"
                                    )}
                                >
                                    <code className={clsx("font-mono text-[12px] text-primary/90", codeClass)} {...props}>
                                        {children}
                                    </code>
                                </pre>
                            );
                        }

                        return (
                            <code className="rounded bg-elevated px-1 py-0.5 font-mono text-[12px] text-primary/90" {...props}>
                                {children}
                            </code>
                        );
                    },
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}
