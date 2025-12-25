"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
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
    placeholder = "Ask about your knowledge...",
}: ChatComposerProps) {
    const [content, setContent] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = "auto";
            const newHeight = Math.min(textarea.scrollHeight, 160); // Max 4 lines approx
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
        <div className="border-t border-border bg-surface px-6 py-4">
            <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end gap-3 bg-canvas border border-border rounded-lg px-4 py-3 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/10 transition-all">
                    <textarea
                        ref={textareaRef}
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder}
                        disabled={isSending || disabled}
                        rows={1}
                        className="flex-1 resize-none bg-transparent text-body text-primary placeholder:text-tertiary focus:outline-none min-h-[26px] max-h-[160px]"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!canSend}
                        className={clsx(
                            "shrink-0 w-8 h-8 flex items-center justify-center rounded-md transition-all",
                            canSend
                                ? "bg-accent text-white hover:opacity-90"
                                : "bg-border-subtle text-tertiary cursor-not-allowed"
                        )}
                    >
                        {isSending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <ArrowUp className="w-4 h-4" />
                        )}
                    </button>
                </div>
                <p className="text-caption text-tertiary mt-2 text-center">
                    Press Enter to send, Shift+Enter for new line
                </p>
            </div>
        </div>
    );
}
