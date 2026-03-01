"use client";

import { Play, FileText, Globe, StickyNote, MoreHorizontal, ExternalLink, Trash2, RefreshCw } from "lucide-react";
import clsx from "clsx";
import { useState, useRef, useEffect } from "react";
import { LibraryItem, LibraryItemType } from "@/lib/api/library";

interface LibraryCardProps {
  item: LibraryItem;
  viewMode: "grid" | "list";
  onOpen: (item: LibraryItem) => void;
  onDelete: (item: LibraryItem) => void;
  onReprocess?: (item: LibraryItem) => void;
}

const typeConfig: Record<LibraryItemType, { icon: React.ElementType; bg: string; color: string }> = {
  video: { icon: Play, bg: "bg-node-source/12", color: "text-node-source" },
  youtube: { icon: Play, bg: "bg-node-source/12", color: "text-node-source" },
  article: { icon: Globe, bg: "bg-node-concept/12", color: "text-node-concept" },
  web: { icon: Globe, bg: "bg-node-concept/12", color: "text-node-concept" },
  note: { icon: StickyNote, bg: "bg-node-definition/12", color: "text-node-definition" },
  file: { icon: FileText, bg: "bg-warning/14", color: "text-warning" },
};

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  const diffWeek = Math.floor(diffDay / 7);

  if (diffSec < 60) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 7) return `${diffDay} days ago`;
  if (diffWeek === 1) return "1 week ago";
  if (diffWeek < 4) return `${diffWeek} weeks ago`;
  return date.toLocaleDateString();
}

export function LibraryCard({ item, viewMode, onOpen, onDelete, onReprocess }: LibraryCardProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const config = typeConfig[item.type] || typeConfig.article;
  const Icon = config.icon;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (viewMode === "list") {
    return (
      <div
        className="group flex items-center p-4 bg-surface border border-border rounded-2xl hover:border-border-strong hover:bg-[var(--hover-bg)] transition-all cursor-pointer"
        onClick={() => onOpen(item)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className={clsx("w-10 h-10 rounded-lg border border-border flex items-center justify-center flex-shrink-0", config.bg, config.color)}>
          <Icon className="w-5 h-5" />
        </div>

        <div className="flex-1 min-w-0 ml-4">
          <h3 className="text-sm font-medium text-primary truncate">{item.title}</h3>
          <p className="text-xs text-secondary mt-0.5 truncate">{item.url}</p>
        </div>

        <div className="flex items-center gap-4 ml-4">
          {item.conceptCount > 0 && (
            <span className="text-xs text-secondary flex items-center gap-1.5">
              <span className={clsx("w-1.5 h-1.5 rounded-full", config.color.replace("text", "bg"))} />
              {item.conceptCount} concepts
            </span>
          )}
          <span className="text-xs text-tertiary whitespace-nowrap">{formatRelativeTime(item.ingestedAt)}</span>
        </div>

        <ActionMenu
          item={item}
          isOpen={isMenuOpen}
          setIsOpen={setIsMenuOpen}
          refEl={menuRef}
          onOpen={onOpen}
          onDelete={onDelete}
          onReprocess={onReprocess}
        />
      </div>
    );
  }

  return (
    <div
      className="group bg-surface border border-border rounded-2xl overflow-hidden hover:border-border-strong hover:bg-[var(--hover-bg)] transition-all cursor-pointer relative"
      onClick={() => onOpen(item)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className={clsx("h-32 flex items-center justify-center border-b border-border", config.bg)}>
        <div className={clsx("w-14 h-14 rounded-xl border border-border flex items-center justify-center", config.bg, config.color)}>
          <Icon className="w-7 h-7" />
        </div>
      </div>

      <div className="p-4">
        <h3 className="text-sm font-medium text-primary line-clamp-2 mb-2">{item.title}</h3>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {item.conceptCount > 0 && (
              <span className="text-[11px] text-secondary flex items-center gap-1">
                <span className={clsx("w-1.5 h-1.5 rounded-full", config.color.replace("text", "bg"))} />
                {item.conceptCount} concepts
              </span>
            )}
          </div>
          <span className="text-[11px] text-tertiary">{formatRelativeTime(item.ingestedAt)}</span>
        </div>
      </div>

      <ActionMenu
        item={item}
        isOpen={isMenuOpen}
        setIsOpen={setIsMenuOpen}
        refEl={menuRef}
        onOpen={onOpen}
        onDelete={onDelete}
        onReprocess={onReprocess}
        compact
        showTrigger={isHovered || isMenuOpen}
      />

      {isHovered && (
        <div className="absolute inset-0 bg-gradient-to-t from-black/36 via-transparent to-transparent pointer-events-none" />
      )}
    </div>
  );
}

function ActionMenu({
  item,
  isOpen,
  setIsOpen,
  refEl,
  onOpen,
  onDelete,
  onReprocess,
  compact = false,
  showTrigger = true,
}: {
  item: LibraryItem;
  isOpen: boolean;
  setIsOpen: (v: boolean) => void;
  refEl: React.RefObject<HTMLDivElement | null>;
  onOpen: (item: LibraryItem) => void;
  onDelete: (item: LibraryItem) => void;
  onReprocess?: (item: LibraryItem) => void;
  compact?: boolean;
  showTrigger?: boolean;
}) {
  return (
    <div className={clsx("relative", compact ? "absolute top-2 right-2" : "ml-3")} ref={refEl}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className={clsx(
          "rounded-lg transition-all",
          compact ? "p-1.5" : "p-2",
          compact
            ? showTrigger
              ? "bg-surface text-secondary hover:text-primary"
              : "opacity-0"
            : "text-secondary hover:text-primary hover:bg-[var(--hover-bg)]",
        )}
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1 w-40 rounded-lg overflow-hidden z-30 overlay-menu">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onOpen(item);
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-secondary hover:bg-[var(--hover-bg)] hover:text-primary transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            Open
          </button>
          {onReprocess && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReprocess(item);
                setIsOpen(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-secondary hover:bg-[var(--hover-bg)] hover:text-primary transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Re-process
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item);
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-danger hover:bg-danger/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
