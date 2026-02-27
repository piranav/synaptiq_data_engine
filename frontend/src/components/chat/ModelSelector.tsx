"use client";

import { useState, useEffect, useRef } from "react";
import { ChevronDown, Sparkles, Lock } from "lucide-react";
import clsx from "clsx";
import { userService, type ModelInfo } from "@/lib/api/user";

interface ModelSelectorProps {
    selectedModel: string;
    onModelChange: (modelId: string) => void;
}

const PROVIDER_COLORS: Record<string, string> = {
    openai: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    anthropic: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
};

export function ModelSelector({ selectedModel, onModelChange }: ModelSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [models, setModels] = useState<ModelInfo[]>([]);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        userService.listModels().then(setModels).catch(console.error);
    }, []);

    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const selected = models.find((m) => m.id === selectedModel);

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={clsx(
                    "h-7 pl-2 pr-1.5 rounded-md inline-flex items-center gap-1.5",
                    "text-[12px] leading-[16px] text-secondary hover:text-primary",
                    "border border-border hover:bg-[var(--hover-bg)] transition-colors",
                )}
            >
                <Sparkles className="w-3 h-3" strokeWidth={1.5} />
                <span className="max-w-[120px] truncate">{selected?.name || selectedModel}</span>
                <ChevronDown className={clsx("w-3 h-3 transition-transform", isOpen && "rotate-180")} />
            </button>

            {isOpen && models.length > 0 && (
                <div className="absolute bottom-full left-0 mb-1 w-[280px] rounded-lg border border-border bg-surface shadow-elevated z-50 py-1 animation-fade-in-up">
                    <div className="px-3 py-2 border-b border-border">
                        <p className="text-[11px] font-semibold text-secondary uppercase tracking-wider">
                            Select Model
                        </p>
                    </div>
                    {models.map((model) => {
                        const isActive = model.id === selectedModel;
                        const isLocked = model.requires_key;
                        return (
                            <button
                                key={model.id}
                                onClick={() => {
                                    if (!isLocked) {
                                        onModelChange(model.id);
                                        setIsOpen(false);
                                    }
                                }}
                                disabled={isLocked}
                                className={clsx(
                                    "w-full px-3 py-2 text-left flex items-start gap-3 transition-colors",
                                    isActive
                                        ? "bg-accent/8"
                                        : isLocked
                                        ? "opacity-50 cursor-not-allowed"
                                        : "hover:bg-[var(--hover-bg)]"
                                )}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span
                                            className={clsx(
                                                "text-[13px] font-medium",
                                                isActive ? "text-accent" : "text-primary"
                                            )}
                                        >
                                            {model.name}
                                        </span>
                                        <span
                                            className={clsx(
                                                "text-[10px] px-1.5 py-0.5 rounded-full font-medium",
                                                PROVIDER_COLORS[model.provider] || "bg-gray-100 text-gray-600"
                                            )}
                                        >
                                            {model.provider}
                                        </span>
                                    </div>
                                    <p className="text-[11px] text-secondary mt-0.5 truncate">
                                        {isLocked ? "Add API key in Settings to unlock" : model.description}
                                    </p>
                                </div>
                                {isLocked && <Lock className="w-3.5 h-3.5 text-secondary mt-0.5 flex-shrink-0" />}
                                {isActive && !isLocked && (
                                    <div className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 flex-shrink-0" />
                                )}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
