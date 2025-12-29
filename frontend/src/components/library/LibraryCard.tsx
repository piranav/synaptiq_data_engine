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
    video: { icon: Play, bg: "bg-[#34d399]/10", color: "text-[#34d399]" },
    youtube: { icon: Play, bg: "bg-[#34d399]/10", color: "text-[#34d399]" },
    article: { icon: Globe, bg: "bg-[#60a5fa]/10", color: "text-[#60a5fa]" },
    web: { icon: Globe, bg: "bg-[#60a5fa]/10", color: "text-[#60a5fa]" },
    note: { icon: StickyNote, bg: "bg-[#a78bfa]/10", color: "text-[#a78bfa]" },
    file: { icon: FileText, bg: "bg-[#fbbf24]/10", color: "text-[#fbbf24]" },
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

    // Close menu when clicking outside
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
                className="group flex items-center p-4 bg-white/[0.02] border border-white/10 rounded-2xl hover:border-white/20 hover:bg-white/[0.04] transition-all cursor-pointer"
                onClick={() => onOpen(item)}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                {/* Icon */}
                <div className={clsx("w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0", config.bg, config.color)}>
                    <Icon className="w-5 h-5" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 ml-4">
                    <h3 className="text-sm font-medium text-white truncate">{item.title}</h3>
                    <p className="text-xs text-white/50 mt-0.5 truncate">{item.url}</p>
                </div>

                {/* Meta */}
                <div className="flex items-center gap-4 ml-4">
                    {item.conceptCount > 0 && (
                        <span className="text-xs text-white/50 flex items-center gap-1.5">
                            <span className={clsx("w-1.5 h-1.5 rounded-full", config.bg.replace("/10", ""))} />
                            {item.conceptCount} concepts
                        </span>
                    )}
                    <span className="text-xs text-white/40 whitespace-nowrap">{formatRelativeTime(item.ingestedAt)}</span>
                </div>

                {/* Menu */}
                <div className="relative ml-3" ref={menuRef}>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsMenuOpen(!isMenuOpen);
                        }}
                        className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06] transition-all"
                    >
                        <MoreHorizontal className="w-4 h-4" />
                    </button>

                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-40 bg-[#1C1C1E] border border-white/10 rounded-lg shadow-lg overflow-hidden z-30">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onOpen(item);
                                    setIsMenuOpen(false);
                                }}
                                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-white/70 hover:bg-white/[0.06] hover:text-white transition-colors"
                            >
                                <ExternalLink className="w-4 h-4" />
                                Open
                            </button>
                            {onReprocess && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onReprocess(item);
                                        setIsMenuOpen(false);
                                    }}
                                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-white/70 hover:bg-white/[0.06] hover:text-white transition-colors"
                                >
                                    <RefreshCw className="w-4 h-4" />
                                    Re-process
                                </button>
                            )}
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDelete(item);
                                    setIsMenuOpen(false);
                                }}
                                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-rose-400 hover:bg-rose-500/10 transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                                Delete
                            </button>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Grid view
    return (
        <div
            className="group bg-white/[0.02] border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 hover:bg-white/[0.04] transition-all cursor-pointer relative"
            onClick={() => onOpen(item)}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* Thumbnail area */}
            <div className={clsx("h-32 flex items-center justify-center", config.bg.replace("/10", "/5"))}>
                <div className={clsx("w-14 h-14 rounded-xl flex items-center justify-center", config.bg, config.color)}>
                    <Icon className="w-7 h-7" />
                </div>
            </div>

            {/* Content */}
            <div className="p-4">
                <h3 className="text-sm font-medium text-white line-clamp-2 mb-2">{item.title}</h3>

                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        {item.conceptCount > 0 && (
                            <span className="text-[11px] text-white/50 flex items-center gap-1">
                                <span className={clsx("w-1.5 h-1.5 rounded-full", config.bg.replace("/10", ""))} />
                                {item.conceptCount} concepts
                            </span>
                        )}
                    </div>
                    <span className="text-[11px] text-white/40">{formatRelativeTime(item.ingestedAt)}</span>
                </div>
            </div>

            {/* Menu button */}
            <div className="absolute top-2 right-2" ref={menuRef}>
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        setIsMenuOpen(!isMenuOpen);
                    }}
                    className={clsx(
                        "p-1.5 rounded-lg transition-all",
                        isHovered || isMenuOpen
                            ? "bg-black/40 text-white/80 hover:text-white"
                            : "opacity-0"
                    )}
                >
                    <MoreHorizontal className="w-4 h-4" />
                </button>

                {isMenuOpen && (
                    <div className="absolute right-0 top-full mt-1 w-40 bg-[#1C1C1E] border border-white/10 rounded-lg shadow-lg overflow-hidden z-30">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onOpen(item);
                                setIsMenuOpen(false);
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-white/70 hover:bg-white/[0.06] hover:text-white transition-colors"
                        >
                            <ExternalLink className="w-4 h-4" />
                            Open
                        </button>
                        {onReprocess && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onReprocess(item);
                                    setIsMenuOpen(false);
                                }}
                                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-white/70 hover:bg-white/[0.06] hover:text-white transition-colors"
                            >
                                <RefreshCw className="w-4 h-4" />
                                Re-process
                            </button>
                        )}
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onDelete(item);
                                setIsMenuOpen(false);
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-rose-400 hover:bg-rose-500/10 transition-colors"
                        >
                            <Trash2 className="w-4 h-4" />
                            Delete
                        </button>
                    </div>
                )}
            </div>

            {/* Hover overlay with quick actions */}
            {isHovered && (
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none" />
            )}
        </div>
    );
}
