"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { ArrowUp, Loader2, Sparkles } from "lucide-react";
import clsx from "clsx";

interface ChatComposerProps {
    onSend: (content: string) => void;
    isSending: boolean;
    disabled?: boolean;
    placeholder?: string;
}

export function ChatComposer({
    onSend,
    isSending,
    disabled = false,
    placeholder = "Ask anything…",
}: ChatComposerProps) {
    const [content, setContent] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = "auto";
            const newHeight = Math.min(textarea.scrollHeight, 120);
            textarea.style.height = `${newHeight}px`;
        }
    }, [content]);

    const handleSend = () => {
        const trimmed = content.trim();
        if (!trimmed || isSending || disabled) return;
        onSend(trimmed);
        setContent("");
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const canSend = content.trim().length > 0 && !isSending && !disabled;

    return (
        <div className="w-full border-t border-white/10 px-4 md:px-8 lg:px-16 py-3 bg-black/20 backdrop-blur">
            <div className="max-w-3xl mx-auto w-full">
                <div className="flex items-end gap-2">
                    {/* Input Area */}
                    <div
                        className={clsx(
                            "flex-1 rounded-md border border-white/10 bg-white/[0.02] p-2",
                            "focus-within:ring-2 focus-within:ring-[#256BEE]/50 focus-within:border-[#256BEE]/50",
                            "transition-all"
                        )}
                    >
                        <textarea
                            ref={textareaRef}
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={placeholder}
                            disabled={isSending || disabled}
                            rows={1}
                            className="w-full bg-transparent outline-none resize-none text-[13px] leading-[18px] text-white placeholder-white/40 min-h-[26px] max-h-[120px]"
                        />
                        {/* Hints */}
                        <div className="mt-1 flex items-center gap-4">
                            <div className="flex items-center gap-1 text-[12px] leading-[16px] text-white/50">
                                <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
                                <span>⌘Enter to send</span>
                            </div>
                        </div>
                    </div>

                    {/* Send Button */}
                    <button
                        onClick={handleSend}
                        disabled={!canSend}
                        className={clsx(
                            "h-9 px-3 rounded-md text-[13px] leading-[18px] font-medium transition-all",
                            "border border-white/10",
                            canSend
                                ? "bg-[#256BEE] hover:bg-[#1F5BCC] text-white"
                                : "bg-white/[0.03] text-white/40 cursor-not-allowed"
                        )}
                    >
                        {isSending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            "Send"
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
