"use client";

import { useState, useEffect } from "react";
import { X, Link as LinkIcon, Loader2, CheckCircle2, Upload, File as FileIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ingestService } from "@/lib/api/ingest";
import clsx from "clsx";

interface AddSourceModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialTab?: "url" | "file";
}

export function AddSourceModal({ isOpen, onClose, initialTab = "url" }: AddSourceModalProps) {
    const [activeTab, setActiveTab] = useState<"url" | "file">(initialTab);
    const [url, setUrl] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [dragActive, setDragActive] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setActiveTab(initialTab);
        }
    }, [isOpen, initialTab]);

    if (!isOpen) return null;

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const droppedFile = e.dataTransfer.files[0];
            if (droppedFile.type === "application/pdf" || droppedFile.name.endsWith(".docx")) {
                setFile(droppedFile);
                setError(null);
            } else {
                setError("Only PDF and DOCX files are supported.");
            }
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            if (activeTab === "url") {
                if (!url) return;
                await ingestService.ingestUrl(url);
            } else {
                if (!file) return;
                await ingestService.uploadFile(file);
            }

            setSuccess(true);
            setTimeout(() => {
                onClose();
                setSuccess(false);
                setUrl("");
                setFile(null);
            }, 1500);
        } catch (err: any) {
            setError(err.message || "Failed to add source");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animation-fade-in">
            <div className="bg-surface border border-border w-full max-w-md rounded-xl shadow-elevated p-6 relative animation-scale-in">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-tertiary hover:text-primary transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="mb-6">
                    <h2 className="text-title-3 mb-1">Add to Knowledge</h2>
                    <p className="text-body text-secondary">
                        Save content to your knowledge graph.
                    </p>
                </div>

                {/* Tabs */}
                <div className="flex gap-4 border-b border-border/50 mb-6">
                    <button
                        onClick={() => setActiveTab("url")}
                        className={clsx(
                            "pb-2 text-body-small font-medium transition-colors relative",
                            activeTab === "url" ? "text-primary" : "text-tertiary hover:text-secondary"
                        )}
                    >
                        URL
                        {activeTab === "url" && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full" />}
                    </button>
                    <button
                        onClick={() => setActiveTab("file")}
                        className={clsx(
                            "pb-2 text-body-small font-medium transition-colors relative",
                            activeTab === "file" ? "text-primary" : "text-tertiary hover:text-secondary"
                        )}
                    >
                        File Upload
                        {activeTab === "file" && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full" />}
                    </button>
                </div>

                {success ? (
                    <div className="flex flex-col items-center justify-center py-8 text-success animate-in fade-in zoom-in duration-300">
                        <CheckCircle2 className="w-12 h-12 mb-3" />
                        <p className="text-title-3">Added Successfully</p>
                    </div>
                ) : activeTab === "url" ? (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="p-4 bg-canvas rounded-xl flex items-center justify-center mb-2">
                            <LinkIcon className="w-8 h-8 text-secondary/50" />
                        </div>
                        <Input
                            placeholder="https://youtube.com/..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            error={error || undefined}
                            autoFocus
                        />
                        <Button
                            type="submit"
                            variant="primary"
                            className="w-full"
                            isLoading={loading}
                            disabled={!url}
                        >
                            Add URL
                        </Button>
                    </form>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div
                            className={clsx(
                                "border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-colors cursor-pointer",
                                dragActive ? "border-accent bg-accent/5" : "border-border hover:border-border-subtle hover:bg-canvas",
                                error ? "border-danger/50" : ""
                            )}
                            onDragEnter={handleDrag}
                            onDragLeave={handleDrag}
                            onDragOver={handleDrag}
                            onDrop={handleDrop}
                            onClick={() => document.getElementById('file-upload')?.click()}
                        >
                            <input
                                id="file-upload"
                                type="file"
                                className="hidden"
                                accept=".pdf,.docx"
                                onChange={handleFileChange}
                            />

                            {file ? (
                                <div className="text-center">
                                    <FileIcon className="w-10 h-10 text-accent mb-3 mx-auto" />
                                    <p className="text-body font-medium truncate max-w-[200px]">{file.name}</p>
                                    <p className="text-caption text-secondary">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                                </div>
                            ) : (
                                <div className="text-center">
                                    <Upload className="w-10 h-10 text-tertiary mb-3 mx-auto" />
                                    <p className="text-body font-medium">Click or drag file</p>
                                    <p className="text-caption text-secondary mt-1">PDF, DOCX up to 50MB</p>
                                </div>
                            )}
                        </div>

                        {error && <p className="text-caption text-danger text-center">{error}</p>}

                        <Button
                            type="submit"
                            variant="primary"
                            className="w-full"
                            isLoading={loading}
                            disabled={!file}
                        >
                            Upload File
                        </Button>
                    </form>
                )}
            </div>
        </div>
    );
}
