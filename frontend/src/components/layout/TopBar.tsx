"use client";

import { Search } from "lucide-react";
import { usePathname } from "next/navigation";
import clsx from "clsx";

export function TopBar() {
    const pathname = usePathname();

    // specific breadcrumb logic could go here
    const pathSegments = pathname.split("/").filter(Boolean);
    const mainSection = pathSegments[0] ? pathSegments[0].charAt(0).toUpperCase() + pathSegments[0].slice(1) : "Home";
    const subSection = "Overview"; // placeholder for now

    return (
        <header className="sticky top-0 z-10 bg-canvas/90 backdrop-blur-md px-8 h-14 flex items-center justify-between border-b border-transparent">
            <div className="flex items-center gap-2 text-secondary text-sm">
                <span className="text-primary font-medium">{mainSection}</span>
                <span className="text-gray-300">/</span>
                <span className="hover:text-primary transition-colors cursor-pointer">{subSection}</span>
            </div>
            <div className="flex items-center gap-4">
                <button className="flex items-center gap-2 px-3 py-1.5 bg-white/50 border border-black/5 rounded-lg text-xs text-secondary cursor-pointer hover:bg-white transition-all">
                    <Search className="w-3.5 h-3.5" />
                    <span className="mr-2">Search...</span>
                    <span className="bg-black/5 px-1.5 py-0.5 rounded text-[10px]">⌘K</span>
                </button>
            </div>
        </header>
    );
}
