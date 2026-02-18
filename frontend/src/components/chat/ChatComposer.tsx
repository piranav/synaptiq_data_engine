"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";
import clsx from "clsx";

interface ChatComposerProps {
    onSend: (content: string) => void;
    isSending: boolean;
    disabled?: boolean;
    placeholder?: string;
    className?: string;
}

export function ChatComposer({
    onSend,
    isSending,
    disabled = false,
    placeholder = "Ask anything…",
    className,
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
        <div className="sticky bottom-0 z-10 w-full border-t border-border px-4 md:px-6 py-3 bg-canvas/90 backdrop-blur-xl">
            <div className={clsx("w-full", className)}>
                <div className="flex items-end gap-2">
                    {/* Input Area */}
                    <div
                        className={clsx(
                            "flex-1 rounded-md border border-border bg-surface p-2",
                            "focus-within:ring-2 focus-within:ring-accent/30 focus-within:border-accent/50",
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
                            className="w-full bg-transparent outline-none resize-none text-[13px] leading-[18px] text-primary placeholder:text-secondary min-h-[26px] max-h-[120px]"
                        />
                        {/* Hints */}
                        <div className="mt-1 flex items-center gap-4">
                            <div className="flex items-center gap-1 text-[12px] leading-[16px] text-secondary">
                                <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
                                <span>Enter to send · Shift+Enter newline</span>
                            </div>
                        </div>
                    </div>

                    {/* Send Button */}
                    <button
                        onClick={handleSend}
                        disabled={!canSend}
                        className={clsx(
                            "h-9 px-3 rounded-md text-[13px] leading-[18px] font-medium transition-all",
                            "border border-border",
                            canSend
                                ? "bg-accent hover:bg-accent-hover text-white"
                                : "bg-surface text-secondary cursor-not-allowed"
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
