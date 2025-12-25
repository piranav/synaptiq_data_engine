"use client";

import { Brain, Database, ArrowUpRight } from "lucide-react";

const stats = [
    { label: "Concepts", value: "1,284", trend: "+12%", icon: Brain },
    { label: "Sources", value: "342", trend: "+4 this week", icon: Database },
    { label: "Notes", value: "85", trend: "Last edited 2m ago", icon: FileText },
];

import { FileText } from "lucide-react";

export function StatsRow() {
    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {stats.map((stat) => {
                const Icon = stat.icon;
                return (
                    <div key={stat.label} className="bg-surface border border-border rounded-xl p-5 shadow-card hover:shadow-hover transition-shadow duration-200 cursor-default">
                        <div className="flex items-start justify-between mb-4">
                            <div className="p-2 bg-canvas rounded-lg text-accent">
                                <Icon className="w-5 h-5" />
                            </div>
                            <ArrowUpRight className="w-4 h-4 text-tertiary" />
                        </div>
                        <div>
                            <div className="text-display text-[32px] mb-1">{stat.value}</div>
                            <div className="text-body-small text-secondary flex items-center justify-between">
                                <span>{stat.label}</span>
                                <span className="text-success text-caption">{stat.trend}</span>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
