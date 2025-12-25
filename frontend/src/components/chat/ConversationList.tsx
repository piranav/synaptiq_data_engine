"use client";

import { useState } from "react";
import clsx from "clsx";
import { Plus, Search, Trash2, MessageSquare, Loader2 } from "lucide-react";
import type { Conversation } from "@/lib/api/chat";

interface ConversationListProps {
    conversations: Conversation[];
    activeId: string | null;
    isLoading: boolean;
    onSelect: (id: string) => void;
    onNew: () => void;
    onDelete: (id: string) => void;
}

export function ConversationList({
    conversations,
    activeId,
    isLoading,
    onSelect,
    onNew,
    onDelete,
}: ConversationListProps) {
    const [searchQuery, setSearchQuery] = useState("");

    const filteredConversations = conversations.filter((c) =>
        (c.title || c.preview || "")
            .toLowerCase()
            .includes(searchQuery.toLowerCase())
    );

    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return date.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
            });
        } else if (diffDays === 1) {
            return "Yesterday";
        } else if (diffDays < 7) {
            return date.toLocaleDateString("en-US", { weekday: "short" });
        } else {
            return date.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
            });
        }
    };

    return (
        <aside className="w-[280px] h-full border-r border-border bg-surface flex flex-col shrink-0">
            {/* Header */}
            <div className="p-4 border-b border-border-subtle">
                <button
                    onClick={onNew}
                    className="w-full h-10 flex items-center justify-center gap-2 bg-accent text-white rounded-md text-body-small font-medium hover:opacity-90 transition-opacity"
                >
                    <Plus className="w-4 h-4" />
                    New chat
                </button>
            </div>

            {/* Search */}
            <div className="px-4 py-3">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-tertiary" />
                    <input
                        type="text"
                        placeholder="Search conversations..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full h-9 pl-9 pr-3 rounded-md bg-canvas border border-border text-body-small placeholder:text-tertiary focus:outline-none focus:border-accent transition-colors"
                    />
                </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto no-scrollbar">
                {isLoading ? (
                    <div className="flex items-center justify-center h-32">
                        <Loader2 className="w-5 h-5 animate-spin text-secondary" />
                    </div>
                ) : filteredConversations.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 px-4 text-center">
                        <MessageSquare className="w-8 h-8 text-tertiary mb-2" />
                        <p className="text-callout text-secondary">
                            {searchQuery ? "No matching conversations" : "No conversations yet"}
                        </p>
                    </div>
                ) : (
                    <div className="py-1">
                        {filteredConversations.map((conversation) => (
                            <div
                                key={conversation.id}
                                onClick={() => onSelect(conversation.id)}
                                className={clsx(
                                    "group relative mx-2 mb-1 px-3 py-3 rounded-lg cursor-pointer transition-colors",
                                    activeId === conversation.id
                                        ? "bg-accent/10"
                                        : "hover:bg-canvas"
                                )}
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                        <h3
                                            className={clsx(
                                                "text-body-small font-medium truncate",
                                                activeId === conversation.id
                                                    ? "text-accent"
                                                    : "text-primary"
                                            )}
                                        >
                                            {conversation.title || "New conversation"}
                                        </h3>
                                        {conversation.preview && (
                                            <p className="text-callout text-secondary truncate mt-0.5">
                                                {conversation.preview}
                                            </p>
                                        )}
                                    </div>
                                    <span className="text-caption text-tertiary shrink-0">
                                        {formatTime(conversation.updated_at)}
                                    </span>
                                </div>

                                {/* Delete button on hover */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete(conversation.id);
                                    }}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-danger/10 text-secondary hover:text-danger transition-all"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </aside>
    );
}
