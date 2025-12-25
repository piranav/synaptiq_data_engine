"use client";

import { Search, Bell, User } from "lucide-react";
import { usePathname } from "next/navigation";

export function TopBar() {
    const pathname = usePathname();
    const title = pathname.split("/")[1] || "Home";
    const displayTitle = title.charAt(0).toUpperCase() + title.slice(1);

    return (
        <header className="h-[56px] pl-[64px] pr-8 flex items-center justify-between border-b border-border bg-white/80 backdrop-blur-md sticky top-0 z-40">
            <div className="pl-6">
                <h1 className="text-title-3 text-primary">{displayTitle}</h1>
            </div>

            <div className="flex items-center gap-4">
                {/* Command Palette Trigger */}
                <button className="hidden sm:flex items-center h-9 px-3 bg-canvas rounded-lg border border-border text-tertiary w-64 hover:border-accent hover:text-secondary transition-colors group">
                    <Search className="w-4 h-4 mr-2" />
                    <span className="text-callout">Search...</span>
                    <span className="ml-auto text-xs px-1.5 py-0.5 rounded border border-border-subtle bg-surface text-tertiary group-hover:border-accent/20">⌘K</span>
                </button>

                <button className="w-9 h-9 flex items-center justify-center rounded-full text-secondary hover:bg-border-subtle hover:text-primary transition-colors">
                    <Bell className="w-5 h-5" />
                </button>

                <button className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-transparent hover:ring-offset-2 hover:ring-accent transition-all">
                    PK
                </button>
            </div>
        </header>
    );
}
