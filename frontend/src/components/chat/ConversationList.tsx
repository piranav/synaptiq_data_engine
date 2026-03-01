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
      .includes(searchQuery.toLowerCase()),
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
    }
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return date.toLocaleDateString("en-US", { weekday: "short" });

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  if (isCollapsed) {
    return (
      <aside className="w-14 h-full border-r border-border bg-surface/55 flex flex-col items-center py-3 shrink-0">
        <button
          onClick={onToggleCollapse}
          className="h-8 w-8 rounded-md flex items-center justify-center border border-border hover:bg-[var(--hover-bg)] text-secondary hover:text-primary transition-colors"
          title="Expand sidebar"
        >
          <PanelLeft className="w-4 h-4" strokeWidth={1.5} />
        </button>
        <button
          onClick={onNew}
          className="mt-2 h-8 w-8 rounded-md flex items-center justify-center border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] transition-colors"
          title="New chat"
        >
          <Plus className="w-4 h-4" strokeWidth={1.5} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-[280px] h-full border-r border-border bg-surface/55 flex flex-col shrink-0">
      <div className="p-3 border-b border-border">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleCollapse}
            className="h-8 w-8 rounded-md flex items-center justify-center border border-border hover:bg-[var(--hover-bg)] text-secondary hover:text-primary transition-colors shrink-0"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="w-4 h-4" strokeWidth={1.5} />
          </button>
          <button
            onClick={onNew}
            className="flex-1 h-8 flex items-center justify-center gap-2 border border-accent/35 bg-[var(--accent-soft)] hover:bg-[var(--hover-bg)] rounded-md text-[13px] leading-[18px] font-medium text-[var(--accent)] transition-colors"
          >
            <Plus className="w-4 h-4" strokeWidth={1.5} />
            New chat
          </button>
        </div>
      </div>

      <div className="px-3 py-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary" strokeWidth={1.5} />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 pl-8 pr-2 rounded-md bg-surface border border-border text-[12px] leading-[16px] text-primary placeholder:text-secondary focus:outline-none focus:ring-2 focus:ring-accent/35 transition-colors"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-5 h-5 animate-spin text-secondary" />
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 px-4 text-center">
            <MessageSquare className="w-8 h-8 text-secondary mb-2" strokeWidth={1.5} />
            <p className="text-[13px] leading-[18px] text-secondary">
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
                  "group relative mx-2 mb-1 px-3 py-2.5 rounded-md cursor-pointer transition-colors border",
                  activeId === conversation.id
                    ? "bg-[var(--accent-soft)] border-accent/30"
                    : "border-transparent hover:bg-[var(--hover-bg)] hover:border-border",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className={clsx("text-[13px] leading-[18px] font-medium truncate", activeId === conversation.id ? "text-[var(--accent)]" : "text-primary")}> 
                      {conversation.title || "New conversation"}
                    </h3>
                    {conversation.preview && (
                      <p className="text-[12px] leading-[16px] text-secondary truncate mt-0.5">
                        {conversation.preview}
                      </p>
                    )}
                  </div>
                  <div className="relative shrink-0 flex items-center">
                    <span className="text-[11px] leading-[16px] text-secondary group-hover:opacity-0 transition-opacity">
                      {formatTime(conversation.updated_at)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(conversation.id);
                      }}
                      className="absolute inset-0 flex items-center justify-center p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-danger/20 text-secondary hover:text-danger transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
