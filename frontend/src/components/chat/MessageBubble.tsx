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
                    "max-w-[75%] rounded-2xl px-4 py-3",
                    isUser
                        ? "bg-[#3A3A3C] text-white"  // iMessage dark grey for user/received
                        : "bg-[#0A84FF] text-white"   // iMessage blue for AI/sent
                )}
            >
                {/* Message Content */}
                <div
                    className={clsx(
                        "text-body whitespace-pre-wrap break-words text-white"
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
                    <div className="mt-3 pt-3 border-t border-white/20">
                        {/* Actions */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleCopy}
                                className="flex items-center gap-1.5 px-2 py-1 text-callout text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors"
                            >
                                {copied ? (
                                    <Check className="w-3.5 h-3.5 text-white" />
                                ) : (
                                    <Copy className="w-3.5 h-3.5" />
                                )}
                                {copied ? "Copied" : "Copy"}
                            </button>

                            {message.concepts_referenced && message.concepts_referenced.length > 0 && (
                                <button className="flex items-center gap-1.5 px-2 py-1 text-callout text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors">
                                    <Network className="w-3.5 h-3.5" />
                                    View in graph
                                </button>
                            )}

                            {message.citations && message.citations.length > 0 && (
                                <button
                                    onClick={() => setShowSources(!showSources)}
                                    className="flex items-center gap-1.5 px-2 py-1 text-callout text-white/70 hover:text-white hover:bg-white/10 rounded transition-colors ml-auto"
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
                                        className="flex items-start gap-3 p-2 bg-white/10 rounded-md"
                                    >
                                        <span className="flex items-center justify-center min-w-[22px] h-[22px] text-caption font-medium bg-white/20 text-white rounded">
                                            {index + 1}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="text-callout font-medium text-white truncate">
                                                {citation.title || citation.source_title || "Unknown Source"}
                                            </h4>
                                            {citation.chunk_text && (
                                                <p className="text-caption text-white/70 line-clamp-2 mt-0.5">
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
                                <div className="flex-1 h-1 bg-white/20 rounded-full overflow-hidden">
                                    <div
                                        className={clsx(
                                            "h-full rounded-full transition-all",
                                            message.confidence >= 0.7
                                                ? "bg-green-400"
                                                : message.confidence >= 0.4
                                                    ? "bg-yellow-400"
                                                    : "bg-red-400"
                                        )}
                                        style={{ width: `${message.confidence * 100}%` }}
                                    />
                                </div>
                                <span className="text-caption text-white/70">
                                    {Math.round(message.confidence * 100)}% confidence
                                </span>
                            </div>
                        )}
                    </div>
                )}

                {/* Timestamp */}
                <p
                    className="text-caption mt-2 text-white/70"
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
