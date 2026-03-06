"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";
import clsx from "clsx";
import { ModelSelector, type ModelOption } from "./ModelSelector";

interface ChatComposerProps {
  onSend: (content: string, modelId: string) => void;
  isSending: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  models: ModelOption[];
  selectedModelId: string;
  onModelChange: (modelId: string) => void;
}

export function ChatComposer({
  onSend,
  isSending,
  disabled = false,
  placeholder = "Ask anything\u2026",
  className,
  models,
  selectedModelId,
  onModelChange,
}: ChatComposerProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    onSend(trimmed, selectedModelId);
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
    <div className="sticky bottom-0 z-10 w-full border-t border-border px-4 md:px-6 py-3 bg-[var(--canvas)]">
      <div className={clsx("w-full", className)}>
        <div className="flex items-end gap-2">
          <div
            className={clsx(
              "flex-1 rounded-xl border border-border bg-surface p-2.5",
              "focus-within:ring-2 focus-within:ring-accent/30 focus-within:border-accent/45",
              "transition-all",
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
            <div className="mt-1 flex items-center gap-4">
              <ModelSelector
                models={models}
                selectedModelId={selectedModelId}
                onSelect={onModelChange}
                disabled={isSending}
              />
              <div className="flex items-center gap-1 text-[12px] leading-[16px] text-secondary">
                <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
                <span>Enter to send</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleSend}
            disabled={!canSend}
            className={clsx(
              "h-10 px-3.5 rounded-xl text-[13px] leading-[18px] font-medium transition-all border",
              canSend
                ? "border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] hover:bg-[var(--hover-bg)]"
                : "border-border bg-surface text-secondary cursor-not-allowed",
            )}
          >
            {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
