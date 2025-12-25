"use client";

import { useState } from "react";
import clsx from "clsx";
import { Copy, Check, Network, ChevronDown, ChevronUp } from "lucide-react";
import type { Message, Citation } from "@/lib/api/chat";
import { CitationChip } from "./CitationChip";

interface MessageBubbleProps {
    message: Message;
    isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
    const [copied, setCopied] = useState(false);
    const [showSources, setShowSources] = useState(false);
    const isUser = message.role === "user";

    const handleCopy = async () => {
        await navigator.clipboard.writeText(message.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // Parse content for citation references like [1], [2]
    const renderContent = (content: string, citations: Citation[]) => {
        if (!citations || citations.length === 0) {
            return <span>{content}</span>;
        }

        // Split by citation patterns [1], [2], etc.
        const parts = content.split(/(\[\d+\])/g);

        return parts.map((part, i) => {
            const match = part.match(/\[(\d+)\]/);
            if (match) {
                const index = parseInt(match[1], 10) - 1;
                const citation = citations[index];
                if (citation) {
                    return <CitationChip key={i} index={index} citation={citation} />;
                }
            }
            return <span key={i}>{part}</span>;
        });
    };

    return (
        <div
            className={clsx(
                "flex w-full",
                isUser ? "justify-end" : "justify-start"
            )}
        >
            <div
                className={clsx(
                    "max-w-[75%] rounded-lg px-4 py-3",
                    isUser
                        ? "bg-accent text-white"
                        : "bg-surface border border-border-subtle"
                )}
            >
                {/* Message Content */}
                <div
                    className={clsx(
                        "text-body whitespace-pre-wrap break-words",
                        isUser ? "text-white" : "text-primary"
                    )}
                >
                    {isUser
                        ? message.content
                        : renderContent(message.content, message.citations)}
                    {isStreaming && (
                        <span className="inline-block w-2 h-4 ml-1 bg-current animate-pulse" />
                    )}
                </div>

                {/* Assistant message extras */}
                {!isUser && !isStreaming && (
                    <div className="mt-3 pt-3 border-t border-border-subtle">
                        {/* Actions */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleCopy}
                                className="flex items-center gap-1.5 px-2 py-1 text-callout text-secondary hover:text-primary hover:bg-canvas rounded transition-colors"
                            >
                                {copied ? (
                                    <Check className="w-3.5 h-3.5 text-success" />
                                ) : (
                                    <Copy className="w-3.5 h-3.5" />
                                )}
                                {copied ? "Copied" : "Copy"}
                            </button>

                            {message.concepts_referenced && message.concepts_referenced.length > 0 && (
                                <button className="flex items-center gap-1.5 px-2 py-1 text-callout text-secondary hover:text-primary hover:bg-canvas rounded transition-colors">
                                    <Network className="w-3.5 h-3.5" />
                                    View in graph
                                </button>
                            )}

                            {message.citations && message.citations.length > 0 && (
                                <button
                                    onClick={() => setShowSources(!showSources)}
                                    className="flex items-center gap-1.5 px-2 py-1 text-callout text-secondary hover:text-primary hover:bg-canvas rounded transition-colors ml-auto"
                                >
                                    {message.citations.length} source{message.citations.length > 1 ? "s" : ""}
                                    {showSources ? (
                                        <ChevronUp className="w-3.5 h-3.5" />
                                    ) : (
                                        <ChevronDown className="w-3.5 h-3.5" />
                                    )}
                                </button>
                            )}
                        </div>

                        {/* Sources Panel */}
                        {showSources && message.citations && message.citations.length > 0 && (
                            <div className="mt-3 space-y-2">
                                {message.citations.map((citation, index) => (
                                    <div
                                        key={index}
                                        className="flex items-start gap-3 p-2 bg-canvas rounded-md"
                                    >
                                        <span className="flex items-center justify-center min-w-[22px] h-[22px] text-caption font-medium bg-accent/15 text-accent rounded">
                                            {index + 1}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="text-callout font-medium text-primary truncate">
                                                {citation.title || citation.source_title || "Unknown Source"}
                                            </h4>
                                            {citation.chunk_text && (
                                                <p className="text-caption text-secondary line-clamp-2 mt-0.5">
                                                    {citation.chunk_text}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Confidence indicator */}
                        {message.confidence !== undefined && message.confidence !== null && (
                            <div className="mt-2 flex items-center gap-2">
                                <div className="flex-1 h-1 bg-border-subtle rounded-full overflow-hidden">
                                    <div
                                        className={clsx(
                                            "h-full rounded-full transition-all",
                                            message.confidence >= 0.7
                                                ? "bg-success"
                                                : message.confidence >= 0.4
                                                    ? "bg-warning"
                                                    : "bg-danger"
                                        )}
                                        style={{ width: `${message.confidence * 100}%` }}
                                    />
                                </div>
                                <span className="text-caption text-tertiary">
                                    {Math.round(message.confidence * 100)}% confidence
                                </span>
                            </div>
                        )}
                    </div>
                )}

                {/* Timestamp */}
                <p
                    className={clsx(
                        "text-caption mt-2",
                        isUser ? "text-white/70" : "text-tertiary"
                    )}
                >
                    {new Date(message.created_at).toLocaleTimeString("en-US", {
                        hour: "numeric",
                        minute: "2-digit",
                    })}
                </p>
            </div>
        </div>
    );
}
