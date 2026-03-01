"use client";

import { useState } from "react";
import clsx from "clsx";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import type { Message } from "@/lib/api/chat";
import { MarkdownMessage } from "./MarkdownMessage";
import { IconFrame } from "@/components/ui/IconFrame";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  className?: string;
}

export function MessageBubble({ message, isStreaming = false, className }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";
  const citationAnchorPrefix = `message-${message.id}`;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <div className={clsx("w-full", className)}>
      <div className="mb-1 text-[12px] leading-[16px] text-secondary">
        {isUser ? "You" : "Synaptiq"} • {formatTime(message.created_at)}
      </div>

      <div
        className={clsx(
          "rounded-xl border",
          isUser
            ? "border-accent/25 bg-[var(--accent-soft)]"
            : "border-border bg-surface",
        )}
      >
        <div className="p-4">
          {isUser ? (
            <div className="text-[13px] leading-[21px] text-primary whitespace-pre-wrap break-words">
              {message.content}
            </div>
          ) : (
            <MarkdownMessage content={message.content} citationAnchorPrefix={citationAnchorPrefix} />
          )}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-primary/50 animate-pulse" />
          )}
        </div>

        {!isUser && !isStreaming && (
          <div className="border-t border-border">
            <div className="px-4 py-3 flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="h-8 px-2.5 rounded-md border border-border bg-elevated hover:bg-[var(--hover-bg)] text-[12px] leading-[16px] text-secondary hover:text-primary flex items-center gap-1.5 transition-colors"
              >
                <IconFrame
                  icon={copied ? Check : Copy}
                  size="sm"
                  tone={copied ? "source" : "neutral"}
                  className="w-6 h-6 rounded-md border-transparent"
                  iconClassName="w-3.5 h-3.5"
                />
                {copied ? "Copied" : "Copy"}
              </button>

              {message.citations && message.citations.length > 0 && (
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="h-8 px-2.5 rounded-md border border-border bg-elevated hover:bg-[var(--hover-bg)] text-[12px] leading-[16px] text-secondary hover:text-primary flex items-center gap-1.5 transition-colors ml-auto"
                >
                  {message.citations.length} source{message.citations.length > 1 ? "s" : ""}
                  {showSources ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>

            {showSources && message.citations && message.citations.length > 0 && (
              <div className="border-t border-border p-3 space-y-2">
                {message.citations.map((citation, index) => (
                  <div
                    id={`${citationAnchorPrefix}-citation-${index + 1}`}
                    key={index}
                    className="p-3 rounded-md border border-border bg-elevated hover:bg-[var(--hover-bg)] transition-colors scroll-mt-24"
                  >
                    <div className="flex items-start gap-3">
                      <span className="flex items-center justify-center min-w-[24px] h-[24px] text-[11px] font-medium bg-canvas/50 text-primary/80 rounded border border-border">
                        {index + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-[13px] leading-[18px] font-medium text-primary truncate">
                          {citation.title || citation.source_title || "Unknown Source"}
                        </h4>
                        {citation.chunk_text && (
                          <p className="text-[12px] leading-[16px] text-secondary line-clamp-2 mt-1">
                            {citation.chunk_text}
                          </p>
                        )}
                        {(citation.url || citation.source_url) && (
                          <a
                            href={citation.url || citation.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block mt-1 text-[12px] text-[var(--accent)] hover:underline"
                          >
                            Open source
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {message.confidence !== undefined && message.confidence !== null && (
              <div className="border-t border-border p-3 flex items-center gap-2">
                <span className="text-[12px] leading-[16px] text-secondary">Confidence</span>
                <span
                  className={clsx(
                    "px-1.5 py-0.5 rounded text-[11px] font-medium border",
                    message.confidence >= 0.7
                      ? "bg-success/12 border-success/30 text-success"
                      : message.confidence >= 0.4
                        ? "bg-warning/12 border-warning/30 text-warning"
                        : "bg-danger/12 border-danger/30 text-danger",
                  )}
                >
                  {Math.round(message.confidence * 100)}%
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
