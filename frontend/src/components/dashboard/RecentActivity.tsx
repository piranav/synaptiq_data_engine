"use client";

import { PlayCircle, FileText, Globe } from "lucide-react";
import clsx from "clsx";

const activities = [
    {
        id: 1,
        type: "video",
        title: "Understanding Hyperbolic Geometry in Neural Networks",
        source: "YouTube",
        time: "2 hours ago",
        icon: PlayCircle,
    },
    {
        id: 2,
        type: "article",
        title: "The Future of Personal Knowledge Graphs",
        source: "KDNuggets",
        time: "5 hours ago",
        icon: Globe,
    },
    {
        id: 3,
        type: "note",
        title: "Meeting Notes: Q4 Planning",
        source: "Notes",
        time: "Yesterday",
        icon: FileText,
    },
    {
        id: 4,
        type: "video",
        title: "Introduction to Graph Theory",
        source: "Coursera",
        time: "2 days ago",
        icon: PlayCircle,
    },
    {
        id: 5,
        type: "article",
        title: "Vector Databases Explained",
        source: "Medium",
        time: "3 days ago",
        icon: Globe,
    },
];

export function RecentActivity() {
    return (
        <div className="bg-surface border border-border rounded-xl shadow-card overflow-hidden">
            <div className="p-4 border-b border-border bg-canvas/50">
                <h3 className="text-title-3">Recent Activity</h3>
            </div>
            <div>
                {activities.map((item, i) => {
                    const Icon = item.icon;
                    return (
                        <div
                            key={item.id}
                            className={clsx(
                                "flex items-center p-4 hover:bg-canvas transition-colors cursor-pointer group",
                                i !== activities.length - 1 && "border-b border-border-subtle"
                            )}
                        >
                            <div className={clsx(
                                "w-10 h-10 rounded-lg flex items-center justify-center shrink-0 mr-4",
                                item.type === 'video' && "bg-red-100 text-red-600",
                                item.type === 'article' && "bg-blue-100 text-blue-600",
                                item.type === 'note' && "bg-yellow-100 text-yellow-600",
                            )}>
                                <Icon className="w-5 h-5" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <h4 className="text-body font-medium truncate group-hover:text-accent transition-colors">
                                    {item.title}
                                </h4>
                                <p className="text-caption text-secondary mt-0.5">
                                    {item.source} • {item.time}
                                </p>
                            </div>
                            <div className="text-caption text-tertiary">
                                Added
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="p-3 bg-canvas/30 border-t border-border text-center">
                <button className="text-callout text-accent hover:underline">
                    View all history
                </button>
            </div>
        </div>
    );
}
