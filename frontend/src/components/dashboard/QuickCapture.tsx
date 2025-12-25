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
                className="bg-white/[0.02] rounded-2xl p-1.5 flex items-center transition-all duration-300 border border-white/10 hover:border-white/20 hover:bg-white/[0.04] cursor-text"
                onClick={handleWrapperClick}
            >
                <div className="pl-4 pr-3">
                    <Sparkles className="w-[18px] h-[18px] text-accent" />
                </div>
                <input
                    type="text"
                    placeholder="Paste a URL, drop a file, or start typing a note..."
                    className="flex-1 h-12 bg-transparent border-none outline-none text-white placeholder-white/40 text-base font-normal box-border"
                    readOnly // prevent typing until modal opens for now, or true input
                />
                <div className="flex items-center gap-1.5 pr-1.5">
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-white/70 hover:text-white hover:bg-white/[0.06] hover:border-white/20 transition-all text-xs font-medium">
                        <LinkIcon className="w-3.5 h-3.5" />
                        <span>URL</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-white/70 hover:text-white hover:bg-white/[0.06] hover:border-white/20 transition-all text-xs font-medium">
                        <Upload className="w-3.5 h-3.5" />
                        <span>Upload</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-white/70 hover:text-white hover:bg-white/[0.06] hover:border-white/20 transition-all text-xs font-medium">
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
