"use client";

import { Link as LinkIcon, Upload, StickyNote, Sparkles } from "lucide-react";
import { useState } from "react";
import { AddSourceModal } from "./AddSourceModal";
import { IconFrame } from "@/components/ui/IconFrame";

export function QuickCapture() {
    const [isWrapperOpen, setIsWrapperOpen] = useState(false);
    const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });

    const handleWrapperClick = (e: React.MouseEvent) => {
        setClickPosition({ x: e.clientX, y: e.clientY });
        setIsWrapperOpen(true);
    };

    return (
        <section className="relative">
            <div
                className="dashboard-card rounded-[28px] p-2.5 md:p-3 flex items-center transition-all duration-300 hover:shadow-hover cursor-text"
                onClick={handleWrapperClick}
            >
                <div className="pl-1 pr-2">
                    <IconFrame icon={Sparkles} tone="accent" size="sm" />
                </div>
                <input
                    type="text"
                    placeholder="Paste a URL, drop a file, or start typing a note..."
                    className="flex-1 h-12 bg-transparent border-none outline-none text-primary placeholder:text-secondary text-base font-normal box-border"
                    readOnly // prevent typing until modal opens for now, or true input
                />
                <div className="hidden md:flex items-center gap-1.5 pr-1">
                    <button className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium">
                        <LinkIcon className="w-3.5 h-3.5" />
                        <span>URL</span>
                    </button>
                    <button className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium">
                        <Upload className="w-3.5 h-3.5" />
                        <span>Upload</span>
                    </button>
                    <button className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium">
                        <StickyNote className="w-3.5 h-3.5" />
                        <span>Note</span>
                    </button>
                </div>
            </div>

            <AddSourceModal
                isOpen={isWrapperOpen}
                onClose={() => setIsWrapperOpen(false)}
                clickPosition={clickPosition}
            />
        </section>
    );
}
