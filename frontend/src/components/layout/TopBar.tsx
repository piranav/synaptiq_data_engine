"use client";

import { Search } from "lucide-react";
import { usePathname } from "next/navigation";

export function TopBar() {
    const pathname = usePathname();

    // specific breadcrumb logic could go here
    const pathSegments = pathname.split("/").filter(Boolean);
    const mainSection = pathSegments[0] ? pathSegments[0].charAt(0).toUpperCase() + pathSegments[0].slice(1) : "Home";
    const subSection = "Overview"; // placeholder for now

    return (
        <header className="sticky top-0 z-10 glass border-b border-white/10 px-8 h-14 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
                <span className="text-white font-medium">{mainSection}</span>
                <span className="text-white/40">/</span>
                <span className="text-white/60 hover:text-white transition-colors cursor-pointer">{subSection}</span>
            </div>
            <div className="flex items-center gap-4">
                <button className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.03] border border-white/10 rounded-lg text-xs text-white/70 cursor-pointer hover:bg-white/[0.06] hover:text-white hover:border-white/20 transition-all">
                    <Search className="w-3.5 h-3.5" />
                    <span className="mr-2">Search...</span>
                    <span className="bg-white/10 px-1.5 py-0.5 rounded text-[10px]">⌘K</span>
                </button>
            </div>
        </header>
    );
}
