"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Sparkles, Zap, Brain } from "lucide-react";
import clsx from "clsx";

export interface ModelOption {
  id: string;
  display_name: string;
  provider: "openai" | "anthropic";
  is_reasoning: boolean;
}

interface ModelSelectorProps {
  models: ModelOption[];
  selectedModelId: string;
  onSelect: (modelId: string) => void;
  disabled?: boolean;
  className?: string;
}

const providerColor: Record<string, string> = {
  openai: "text-emerald-500",
  anthropic: "text-orange-400",
};

const providerIcon: Record<string, typeof Sparkles> = {
  openai: Zap,
  anthropic: Sparkles,
};

export function ModelSelector({
  models,
  selectedModelId,
  onSelect,
  disabled = false,
  className,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selected = models.find((m) => m.id === selectedModelId) || models[0];
  if (!selected) return null;

  const Icon = providerIcon[selected.provider] || Sparkles;

  return (
    <div ref={ref} className={clsx("relative inline-block", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          "h-8 pl-2.5 pr-2 rounded-lg border border-border bg-surface text-[12px] leading-[16px] font-medium",
          "inline-flex items-center gap-1.5 transition-all",
          disabled
            ? "opacity-50 cursor-not-allowed"
            : "hover:bg-elevated hover:border-accent/30 cursor-pointer"
        )}
      >
        <Icon className={clsx("w-3.5 h-3.5", providerColor[selected.provider])} />
        <span className="text-primary truncate max-w-[120px]">{selected.display_name}</span>
        {selected.is_reasoning && (
          <Brain className="w-3 h-3 text-violet-400" />
        )}
        <ChevronDown
          className={clsx(
            "w-3 h-3 text-secondary transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div className="absolute bottom-full mb-1 left-0 z-50 min-w-[220px] rounded-xl border border-border bg-[var(--canvas-elevated)] shadow-elevated overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-150">
          {(["openai", "anthropic"] as const).map((provider) => {
            const group = models.filter((m) => m.provider === provider);
            if (group.length === 0) return null;
            const GroupIcon = providerIcon[provider] || Sparkles;
            return (
              <div key={provider}>
                <div className="px-3 pt-2.5 pb-1 text-[11px] leading-[14px] font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5">
                  <GroupIcon className={clsx("w-3 h-3", providerColor[provider])} />
                  {provider === "openai" ? "OpenAI" : "Anthropic"}
                </div>
                {group.map((m) => {
                  const isActive = m.id === selectedModelId;
                  return (
                    <button
                      key={m.id}
                      onClick={() => {
                        onSelect(m.id);
                        setOpen(false);
                      }}
                      className={clsx(
                        "w-full text-left px-3 py-2 text-[13px] leading-[18px] flex items-center gap-2 transition-colors",
                        isActive
                          ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                          : "text-primary hover:bg-[var(--hover-bg)]"
                      )}
                    >
                      <span className="flex-1">{m.display_name}</span>
                      {m.is_reasoning && (
                        <span className="text-[10px] leading-[14px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 font-medium">
                          thinking
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
