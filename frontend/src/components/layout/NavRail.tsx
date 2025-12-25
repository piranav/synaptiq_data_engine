"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Home,
    Share2,
    FileText,
    Library,
    MessageSquare,
    Settings,
    Plus
} from "lucide-react";
import clsx from "clsx";

const navItems = [
    { label: "Home", icon: Home, href: "/home" },
    { label: "Graph", icon: Share2, href: "/graph" },
    { label: "Notes", icon: FileText, href: "/notes" },
    { label: "Library", icon: Library, href: "/library" },
    { label: "Chat", icon: MessageSquare, href: "/chat" },
];

export function NavRail() {
    const pathname = usePathname();

    return (
        <nav className="group flex flex-col h-screen fixed left-0 top-0 bottom-0 bg-surface border-r border-border z-50 transition-all duration-300 w-[64px] hover:w-[240px] overflow-hidden shadow-card hover:shadow-elevated">
            {/* Logo Area */}
            <div className="flex items-center h-[56px] px-[18px]">
                <div className="w-7 h-7 bg-black rounded-lg flex items-center justify-center shrink-0">
                    <div className="w-4 h-4 rounded-full border border-white/50" />
                </div>
                <span className="ml-4 font-semibold text-[17px] opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap">
                    Synaptiq
                </span>
            </div>

            {/* Main Nav */}
            <div className="flex-1 py-4 flex flex-col gap-1 px-2">
                {navItems.map((item) => {
                    const isActive = pathname.startsWith(item.href);
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={clsx(
                                "flex items-center h-10 px-3 rounded-lg transition-colors duration-200",
                                isActive
                                    ? "bg-black text-white"
                                    : "text-secondary hover:bg-border-subtle hover:text-primary"
                            )}
                        >
                            <Icon className="w-5 h-5 shrink-0" strokeWidth={isActive ? 2.5 : 2} />
                            <span className="ml-4 text-[15px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap delay-75">
                                {item.label}
                            </span>
                        </Link>
                    );
                })}
            </div>

            {/* Bottom Actions */}
            <div className="p-2 border-t border-border-subtle flex flex-col gap-1">
                <button className="flex items-center h-10 px-3 rounded-lg text-secondary hover:bg-border-subtle hover:text-primary transition-colors duration-200 w-full text-left">
                    <Plus className="w-5 h-5 shrink-0" />
                    <span className="ml-4 text-[15px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap delay-75">
                        Quick Add
                    </span>
                </button>
                <Link
                    href="/settings"
                    className={clsx(
                        "flex items-center h-10 px-3 rounded-lg transition-colors duration-200",
                        pathname.startsWith("/settings")
                            ? "bg-black text-white"
                            : "text-secondary hover:bg-border-subtle hover:text-primary"
                    )}
                >
                    <Settings className="w-5 h-5 shrink-0" />
                    <span className="ml-4 text-[15px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap delay-75">
                        Settings
                    </span>
                </Link>
            </div>
        </nav>
    );
}
