"use client";

import { Link as LinkIcon, Upload, FileText, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useState } from "react";
import { AddSourceModal } from "./AddSourceModal";

export function QuickCapture() {
    const [isModalOpen, setIsModalOpen] = useState(false);

    return (
        <>
            <div className="bg-surface border border-border rounded-xl shadow-card p-6 mb-8">
                <div className="flex flex-col gap-4">
                    <input
                        type="text"
                        placeholder="Add to your knowledge..."
                        className="text-title-2 bg-transparent border-none placeholder:text-tertiary focus:outline-none w-full"
                        onClick={() => setIsModalOpen(true)}
                    />

                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="gap-2 text-secondary"
                            onClick={() => setIsModalOpen(true)}
                        >
                            <LinkIcon className="w-4 h-4" />
                            <span>URL</span>
                        </Button>
                        <Button variant="ghost" size="sm" className="gap-2 text-secondary">
                            <Upload className="w-4 h-4" />
                            <span>Upload</span>
                        </Button>
                        <Button variant="ghost" size="sm" className="gap-2 text-secondary">
                            <FileText className="w-4 h-4" />
                            <span>Note</span>
                        </Button>
                        <div className="flex-1" />
                        <Button
                            variant="primary"
                            size="sm"
                            className="rounded-full"
                            onClick={() => setIsModalOpen(true)}
                        >
                            <ArrowRight className="w-4 h-4" />
                        </Button>
                    </div>
                </div>
            </div>

            <AddSourceModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
            />
        </>
    );
}
