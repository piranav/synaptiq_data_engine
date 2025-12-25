"use client";

import { useState } from "react";
import { X, Link as LinkIcon, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ingestService } from "@/lib/api/ingest";
import clsx from "clsx";

interface AddSourceModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function AddSourceModal({ isOpen, onClose }: AddSourceModalProps) {
    const [url, setUrl] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!url) return;

        setLoading(true);
        setError(null);

        try {
            await ingestService.ingestUrl(url);
            setSuccess(true);
            setTimeout(() => {
                onClose();
                setSuccess(false);
                setUrl("");
            }, 1500);
        } catch (err: any) {
            setError(err.message || "Failed to add source");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animation-fade-in">
            <div className="bg-surface border border-border w-full max-w-md rounded-2xl shadow-elevated p-6 relative animation-scale-in">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-tertiary hover:text-primary transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="mb-6">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
                        <LinkIcon className="w-5 h-5 text-accent" />
                    </div>
                    <h2 className="text-title-3 mb-1">Add to Knowledge</h2>
                    <p className="text-body text-secondary">
                        Save a URL to your knowledge graph. We support YouTube videos and web articles.
                    </p>
                </div>

                {success ? (
                    <div className="flex flex-col items-center justify-center py-8 text-success animate-in fade-in zoom-in duration-300">
                        <CheckCircle2 className="w-12 h-12 mb-3" />
                        <p className="text-title-3">Added Successfully</p>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <Input
                            label="URL"
                            placeholder="https://..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            error={error || undefined}
                            autoFocus
                        />

                        <div className="flex justify-end gap-3 pt-2">
                            <Button type="button" variant="ghost" onClick={onClose}>
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                variant="primary"
                                isLoading={loading}
                                disabled={!url}
                            >
                                Add Source
                            </Button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
}
