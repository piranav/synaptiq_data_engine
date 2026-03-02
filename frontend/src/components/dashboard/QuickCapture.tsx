"use client";

import { Link as LinkIcon, Upload, StickyNote, Sparkles } from "lucide-react";
import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AddSourceModal } from "./AddSourceModal";
import { IconFrame } from "@/components/ui/IconFrame";

const WORD_THRESHOLD = 8;
const URL_REGEX = /^https?:\/\/\S+$/i;

export function QuickCapture() {
    const router = useRouter();
    const [inputValue, setInputValue] = useState("");
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [modalTab, setModalTab] = useState<"url" | "file">("url");
    const inputRef = useRef<HTMLInputElement>(null);

    const wordCount = inputValue.trim().split(/\s+/).filter(Boolean).length;

    const openUrlModal = useCallback(() => {
        setModalTab("url");
        setIsModalOpen(true);
    }, []);

    const openFileModal = useCallback(() => {
        setModalTab("file");
        setIsModalOpen(true);
    }, []);

    const navigateToNotes = useCallback(
        (text: string) => {
            const encoded = encodeURIComponent(text.trim());
            router.push(`/notes?draft=${encoded}`);
        },
        [router],
    );

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        setInputValue(val);

        const words = val.trim().split(/\s+/).filter(Boolean);
        if (words.length >= WORD_THRESHOLD) {
            navigateToNotes(val);
        }
    };

    const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
        const pasted = e.clipboardData.getData("text").trim();
        if (URL_REGEX.test(pasted)) {
            e.preventDefault();
            setInputValue(pasted);
            openUrlModal();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            e.preventDefault();
            const trimmed = inputValue.trim();
            if (!trimmed) return;

            if (URL_REGEX.test(trimmed)) {
                openUrlModal();
            } else {
                navigateToNotes(trimmed);
            }
        }
    };

    const handleNoteClick = () => {
        if (inputValue.trim()) {
            navigateToNotes(inputValue);
        } else {
            router.push("/notes?new=1");
        }
    };

    return (
        <section className="relative">
            <div className="dashboard-card rounded-[14px] p-2.5 md:p-3 flex items-center transition-all duration-300 hover:shadow-hover">
                <div className="pl-1 pr-2">
                    <IconFrame icon={Sparkles} tone="accent" size="sm" />
                </div>
                <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={handleChange}
                    onPaste={handlePaste}
                    onKeyDown={handleKeyDown}
                    placeholder="Paste a URL, drop a file, or start typing a note..."
                    className="flex-1 h-12 bg-transparent border-none outline-none text-primary placeholder:text-secondary text-base font-normal box-border"
                />
                <div className="hidden md:flex items-center gap-1.5 pr-1">
                    <button
                        onClick={openUrlModal}
                        className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium"
                    >
                        <LinkIcon className="w-3.5 h-3.5" />
                        <span>URL</span>
                    </button>
                    <button
                        onClick={openFileModal}
                        className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium"
                    >
                        <Upload className="w-3.5 h-3.5" />
                        <span>Upload</span>
                    </button>
                    <button
                        onClick={handleNoteClick}
                        className="dashboard-pill flex items-center gap-1.5 px-3 py-1.5 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-all text-xs font-medium"
                    >
                        <StickyNote className="w-3.5 h-3.5" />
                        <span>Note</span>
                    </button>
                </div>
            </div>

            <AddSourceModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                initialTab={modalTab}
            />
        </section>
    );
}
