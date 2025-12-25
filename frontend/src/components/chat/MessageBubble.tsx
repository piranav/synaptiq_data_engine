"use client";

import { useState } from "react";
import clsx from "clsx";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
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

    // Format time
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
        });
    };

    return (
        <div className="max-w-3xl">
            {/* Sender Label */}
            <div className="mb-1 text-[12px] leading-[16px] text-white/60">
                {isUser ? "You" : "Synaptiq"} • {formatTime(message.created_at)}
            </div>

            {/* Message Container */}
            <div
                className={clsx(
                    "rounded-lg border border-white/10",
                    isUser ? "bg-white/[0.03]" : "bg-white/[0.02]"
                )}
            >
                {/* Content */}
                <div className="p-3">
                    <div className="text-[13px] leading-[18px] text-white/90 whitespace-pre-wrap break-words">
                        {isUser
                            ? message.content
                            : renderContent(message.content, message.citations)}
                        {isStreaming && (
                            <span className="inline-block w-2 h-4 ml-1 bg-white/60 animate-pulse" />
                        )}
                    </div>
                </div>

                {/* Assistant message extras */}
                {!isUser && !isStreaming && (
                    <div className="border-t border-white/10">
                        {/* Actions Row */}
                        <div className="p-3 flex items-center gap-2">
                            <button
                                onClick={handleCopy}
                                className="h-8 px-2.5 rounded-md border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] text-[12px] leading-[16px] text-white/70 hover:text-white flex items-center gap-1.5 transition-colors"
                            >
                                {copied ? (
                                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                    <Copy className="w-3.5 h-3.5" />
                                )}
                                {copied ? "Copied" : "Copy"}
                            </button>

                            {/* Sources Toggle */}
                            {message.citations && message.citations.length > 0 && (
                                <button
                                    onClick={() => setShowSources(!showSources)}
                                    className="h-8 px-2.5 rounded-md border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] text-[12px] leading-[16px] text-white/70 hover:text-white flex items-center gap-1.5 transition-colors ml-auto"
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

                        {/* Expanded Sources Panel */}
                        {showSources && message.citations && message.citations.length > 0 && (
                            <div className="border-t border-white/10 p-3 space-y-2">
                                {message.citations.map((citation, index) => (
                                    <div
                                        key={index}
                                        className="p-3 rounded-md border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
                                    >
                                        <div className="flex items-start gap-3">
                                            <span className="flex items-center justify-center min-w-[22px] h-[22px] text-[11px] font-medium bg-white/10 text-white/80 rounded">
                                                {index + 1}
                                            </span>
                                            <div className="flex-1 min-w-0">
                                                <h4 className="text-[13px] leading-[18px] font-medium text-white truncate">
                                                    {citation.title || citation.source_title || "Unknown Source"}
                                                </h4>
                                                {citation.chunk_text && (
                                                    <p className="text-[12px] leading-[16px] text-white/60 line-clamp-2 mt-1">
                                                        {citation.chunk_text}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Confidence indicator */}
                        {message.confidence !== undefined && message.confidence !== null && (
                            <div className="border-t border-white/10 p-3 flex items-center gap-2">
                                <span className="text-[12px] leading-[16px] text-white/60">Confidence</span>
                                <span
                                    className={clsx(
                                        "px-1.5 py-0.5 rounded text-[11px] font-medium border",
                                        message.confidence >= 0.7
                                            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                                            : message.confidence >= 0.4
                                                ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                                                : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                                    )}
                                >
                                    {Math.round(message.confidence * 100)}%
                                </span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
