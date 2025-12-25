"use client";

import { useState } from "react";
import clsx from "clsx";
import { Plus, Search, Trash2, MessageSquare, Loader2, PanelLeftClose, PanelLeft } from "lucide-react";
import type { Conversation } from "@/lib/api/chat";

interface ConversationListProps {
    conversations: Conversation[];
    activeId: string | null;
    isLoading: boolean;
    isCollapsed: boolean;
    onSelect: (id: string) => void;
    onNew: () => void;
    onDelete: (id: string) => void;
    onToggleCollapse: () => void;
}

export function ConversationList({
    conversations,
    activeId,
    isLoading,
    isCollapsed,
    onSelect,
    onNew,
    onDelete,
    onToggleCollapse,
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

    // Collapsed state - just show toggle button
    if (isCollapsed) {
        return (
            <aside className="w-14 h-full border-r border-white/10 bg-black/20 flex flex-col items-center py-3 shrink-0">
                <button
                    onClick={onToggleCollapse}
                    className="h-8 w-8 rounded-md flex items-center justify-center border border-white/10 hover:bg-white/[0.06] text-white/70 hover:text-white transition-colors"
                    title="Expand sidebar"
                >
                    <PanelLeft className="w-4 h-4" strokeWidth={1.5} />
                </button>
                <button
                    onClick={onNew}
                    className="mt-2 h-8 w-8 rounded-md flex items-center justify-center bg-[#256BEE] hover:bg-[#1F5BCC] text-white transition-colors"
                    title="New chat"
                >
                    <Plus className="w-4 h-4" strokeWidth={1.5} />
                </button>
            </aside>
        );
    }

    return (
        <aside className="w-[280px] h-full border-r border-white/10 bg-black/20 flex flex-col shrink-0">
            {/* Header */}
            <div className="p-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                    <button
                        onClick={onToggleCollapse}
                        className="h-8 w-8 rounded-md flex items-center justify-center border border-white/10 hover:bg-white/[0.06] text-white/70 hover:text-white transition-colors shrink-0"
                        title="Collapse sidebar"
                    >
                        <PanelLeftClose className="w-4 h-4" strokeWidth={1.5} />
                    </button>
                    <button
                        onClick={onNew}
                        className="flex-1 h-8 flex items-center justify-center gap-2 bg-[#256BEE] hover:bg-[#1F5BCC] rounded-md text-[13px] leading-[18px] font-medium text-white transition-colors border border-white/10"
                    >
                        <Plus className="w-4 h-4" strokeWidth={1.5} />
                        New chat
                    </button>
                </div>
            </div>

            {/* Search */}
            <div className="px-3 py-3">
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/50" strokeWidth={1.5} />
                    <input
                        type="text"
                        placeholder="Search conversations..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full h-8 pl-8 pr-2 rounded-md bg-white/[0.03] border border-white/10 text-[12px] leading-[16px] text-white/80 placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-[#256BEE]/50 transition-colors"
                    />
                </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto no-scrollbar">
                {isLoading ? (
                    <div className="flex items-center justify-center h-32">
                        <Loader2 className="w-5 h-5 animate-spin text-white/60" />
                    </div>
                ) : filteredConversations.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 px-4 text-center">
                        <MessageSquare className="w-8 h-8 text-white/40 mb-2" strokeWidth={1.5} />
                        <p className="text-[13px] leading-[18px] text-white/60">
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
                                    "group relative mx-2 mb-1 px-3 py-2.5 rounded-md cursor-pointer transition-colors border border-transparent",
                                    activeId === conversation.id
                                        ? "bg-white/[0.06] border-white/10"
                                        : "hover:bg-white/[0.04] hover:border-white/10"
                                )}
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                        <h3
                                            className={clsx(
                                                "text-[13px] leading-[18px] font-medium truncate",
                                                activeId === conversation.id
                                                    ? "text-white"
                                                    : "text-white/80"
                                            )}
                                        >
                                            {conversation.title || "New conversation"}
                                        </h3>
                                        {conversation.preview && (
                                            <p className="text-[12px] leading-[16px] text-white/50 truncate mt-0.5">
                                                {conversation.preview}
                                            </p>
                                        )}
                                    </div>
                                    <span className="text-[11px] leading-[16px] text-white/40 shrink-0">
                                        {formatTime(conversation.updated_at)}
                                    </span>
                                </div>

                                {/* Delete button on hover */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete(conversation.id);
                                    }}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-rose-500/20 text-white/60 hover:text-rose-400 transition-all"
                                >
                                    <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </aside>
    );
}
