"use client";

import { Activity, AlertCircle, Clock3 } from "lucide-react";
import type { Job } from "@/lib/api/dashboard";
import { IconFrame } from "@/components/ui/IconFrame";

interface IngestionHealthProps {
    jobs: Job[];
}

function formatAge(iso: string): string {
    const created = new Date(iso).getTime();
    const diffMs = Date.now() - created;
    const mins = Math.floor(diffMs / (1000 * 60));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hours}h ${remMins}m`;
}

export function IngestionHealth({ jobs }: IngestionHealthProps) {
    const processing = jobs.filter((job) => job.status === "processing");
    const failed = jobs.filter((job) => job.status === "failed");
    const queueAge = processing.length > 0
        ? formatAge(processing.reduce((oldest, current) =>
            new Date(current.created_at) < new Date(oldest.created_at) ? current : oldest
        ).created_at)
        : "0m";

    return (
        <section className="dashboard-card rounded-[24px] p-5 h-full">
            <div className="flex items-center gap-2.5 mb-4">
                <IconFrame icon={Activity} tone="accent" />
                <h3 className="text-sm font-semibold text-primary">Ingestion Health</h3>
            </div>

            <div className="grid grid-cols-3 gap-2.5 mb-4">
                <div className="rounded-[14px] border border-border bg-elevated p-2.5">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-secondary">Processing</p>
                    <p className="text-lg font-semibold text-primary mt-1">{processing.length}</p>
                </div>
                <div className="rounded-[14px] border border-border bg-elevated p-2.5">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-secondary">Failed</p>
                    <p className="text-lg font-semibold text-danger mt-1">{failed.length}</p>
                </div>
                <div className="rounded-[14px] border border-border bg-elevated p-2.5">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-secondary">Queue Age</p>
                    <p className="text-lg font-semibold text-primary mt-1">{queueAge}</p>
                </div>
            </div>

            <div className="space-y-2.5">
                {jobs.length === 0 ? (
                    <p className="text-xs text-secondary">No recent ingestion jobs.</p>
                ) : (
                    jobs.slice(0, 4).map((job) => (
                        <div key={job.id} className="rounded-[14px] border border-border-subtle bg-elevated px-3 py-2.5">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-xs text-primary truncate">{job.source_url || "Unknown source"}</p>
                                <span className="text-[10px] text-secondary flex items-center gap-1 shrink-0">
                                    <Clock3 className="w-3 h-3" />
                                    {formatAge(job.created_at)}
                                </span>
                            </div>
                            <p className="text-[10px] text-secondary mt-1 inline-flex items-center gap-1">
                                {job.status === "failed" && <AlertCircle className="w-3 h-3 text-danger" />}
                                {job.status}
                            </p>
                        </div>
                    ))
                )}
            </div>
        </section>
    );
}
