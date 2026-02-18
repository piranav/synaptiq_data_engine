"use client";

import { useMemo } from "react";
import { BarChart3, BookOpen, MessageSquare, Timer } from "lucide-react";
import type { Conversation, Message } from "@/lib/api/chat";
import { IconFrame } from "@/components/ui/IconFrame";

interface ChatContextPanelProps {
    conversation: Conversation | null;
    messages: Message[];
}

interface SourceSummary {
    key: string;
    title: string;
    url?: string;
    count: number;
}

function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function ChatContextPanel({ conversation, messages }: ChatContextPanelProps) {
    const { sources, avgConfidence } = useMemo(() => {
        const sourceMap = new Map<string, SourceSummary>();
        const confidences: number[] = [];

        for (const message of messages) {
            if (typeof message.confidence === "number") {
                confidences.push(message.confidence);
            }
            for (const citation of message.citations || []) {
                const title = citation.title || citation.source_title || "Untitled source";
                const url = citation.url || citation.source_url;
                const key = `${title}:${url || ""}`;
                const existing = sourceMap.get(key);
                if (existing) {
                    existing.count += 1;
                } else {
                    sourceMap.set(key, { key, title, url, count: 1 });
                }
            }
        }

        const avg = confidences.length
            ? Math.round((confidences.reduce((sum, value) => sum + value, 0) / confidences.length) * 100)
            : null;

        return {
            sources: Array.from(sourceMap.values()).sort((a, b) => b.count - a.count),
            avgConfidence: avg,
        };
    }, [messages]);

    const userMessages = messages.filter((m) => m.role === "user").length;

    return (
        <aside className="h-full border-l border-border bg-surface/40 p-4 overflow-y-auto thin-scrollbar">
            <div className="space-y-4">
                <section className="rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <IconFrame icon={MessageSquare} tone="accent" />
                        <h3 className="text-sm font-semibold text-primary">Conversation</h3>
                    </div>
                    <p className="text-[13px] text-primary/90 line-clamp-3">
                        {conversation?.title || "New conversation"}
                    </p>
                    <p className="text-xs text-secondary mt-2">
                        {messages.length} messages
                    </p>
                    {conversation?.updated_at && (
                        <p className="text-xs text-secondary mt-1">
                            Updated {formatDate(conversation.updated_at)}
                        </p>
                    )}
                </section>

                <section className="rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <IconFrame icon={BarChart3} tone="relation" />
                        <h3 className="text-sm font-semibold text-primary">Quality</h3>
                    </div>
                    <div className="space-y-2 text-xs text-secondary">
                        <div className="flex items-center justify-between">
                            <span>Average confidence</span>
                            <span className="text-primary font-medium">
                                {avgConfidence === null ? "N/A" : `${avgConfidence}%`}
                            </span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span>Questions asked</span>
                            <span className="text-primary font-medium">{userMessages}</span>
                        </div>
                    </div>
                </section>

                <section className="rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <IconFrame icon={BookOpen} tone="source" />
                        <h3 className="text-sm font-semibold text-primary">Sources Used</h3>
                    </div>
                    {sources.length === 0 ? (
                        <p className="text-xs text-secondary">No source citations in this conversation yet.</p>
                    ) : (
                        <div className="space-y-2">
                            {sources.slice(0, 8).map((source, index) => (
                                <div key={source.key} className="rounded-lg border border-border-subtle bg-canvas/30 px-3 py-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <span className="text-[12px] text-primary line-clamp-2">{index + 1}. {source.title}</span>
                                        <span className="text-[11px] text-secondary">{source.count}x</span>
                                    </div>
                                    {source.url && (
                                        <a
                                            href={source.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="mt-1 inline-block text-[11px] text-accent hover:underline truncate max-w-full"
                                        >
                                            Open source
                                        </a>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                <section className="rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center gap-2 mb-2">
                        <IconFrame icon={Timer} tone="neutral" />
                        <h3 className="text-sm font-semibold text-primary">Session Tips</h3>
                    </div>
                    <p className="text-xs text-secondary">
                        Use markdown lists and fenced code blocks in prompts to get more structured answers.
                    </p>
                </section>
            </div>
        </aside>
    );
}
