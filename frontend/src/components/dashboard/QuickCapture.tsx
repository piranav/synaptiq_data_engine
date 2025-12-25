"use client";

import { Link as LinkIcon, Upload, StickyNote, Sparkles } from "lucide-react";
import { useState } from "react";
import { AddSourceModal } from "./AddSourceModal";

export function QuickCapture() {
    const [isWrapperOpen, setIsWrapperOpen] = useState(false);
    const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });

    const handleWrapperClick = (e: React.MouseEvent) => {
        setClickPosition({ x: e.clientX, y: e.clientY });
        setIsWrapperOpen(true);
    };

    return (
        <section className="relative group mb-10">
            <div
                className="bg-surface rounded-2xl shadow-glow p-1.5 flex items-center transition-shadow duration-300 hover:shadow-float border border-transparent hover:border-black/5 cursor-text"
                onClick={handleWrapperClick}
            >
                <div className="pl-4 pr-3 text-secondary">
                    <Sparkles className="w-[18px] h-[18px] text-accent" />
                </div>
                <input
                    type="text"
                    placeholder="Paste a URL, drop a file, or start typing a note..."
                    className="flex-1 h-12 bg-transparent border-none outline-none text-primary placeholder-secondary/70 text-base font-normal box-border"
                    readOnly // prevent typing until modal opens for now, or true input
                />
                <div className="flex items-center gap-1.5 pr-1.5">
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas text-secondary hover:text-primary hover:bg-gray-200/50 transition-colors text-xs font-medium">
                        <LinkIcon className="w-3.5 h-3.5" />
                        <span>URL</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas text-secondary hover:text-primary hover:bg-gray-200/50 transition-colors text-xs font-medium">
                        <Upload className="w-3.5 h-3.5" />
                        <span>Upload</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas text-secondary hover:text-primary hover:bg-gray-200/50 transition-colors text-xs font-medium">
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
