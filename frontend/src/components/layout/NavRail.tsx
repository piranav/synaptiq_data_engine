"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
    LayoutGrid,
    Network,
    PenLine,
    Library,
    MessageSquare,
    Settings,
    LogOut,
    Loader2
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "@/contexts/AuthContext";
import { dashboardService } from "@/lib/api/dashboard";
import { useState, useEffect } from "react";
import { authService } from "@/lib/api/auth";

const navItems = [
    { label: "Home", icon: LayoutGrid, href: "/home" },
    { label: "Graph", icon: Network, href: "/graph" },
    { label: "Notes", icon: PenLine, href: "/notes" },
    { label: "Library", icon: Library, href: "/library" },
    { label: "Chat", icon: MessageSquare, href: "/chat" },
];

export function NavRail() {
    const pathname = usePathname();
    const router = useRouter();
    const { user } = useAuth();
    const [isSyncing, setIsSyncing] = useState(false);

    // Poll for sync status
    useEffect(() => {
        const checkSyncStatus = async () => {
            try {
                const jobs = await dashboardService.getActiveJobs();
                setIsSyncing(jobs.length > 0);
            } catch (error) {
                console.error("Failed to check sync status", error);
            }
        };

        checkSyncStatus();
        const interval = setInterval(checkSyncStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    const initials = user?.name
        ? user.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()
        : "PK";

    const handleLogout = async () => {
        try {
            await authService.logout();
            router.push("/login");
        } catch (error) {
            console.error("Logout failed", error);
        }
    };

    return (
        <nav className="group flex flex-col h-screen relative bg-surface border-r border-border z-50 transition-all duration-300 w-16 hover:w-64 overflow-hidden flex-shrink-0 py-6">
            {/* Logo Area */}
            <div className="mb-8 w-full flex justify-center group-hover:justify-start group-hover:px-6 transition-all duration-300">
                <div className="w-8 h-8 bg-primary text-white flex items-center justify-center rounded-lg text-sm font-semibold tracking-tight shrink-0">
                    S
                </div>
                <span className="hidden group-hover:block ml-3 font-semibold text-primary self-center tracking-tight whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-300 delay-100">
                    Synaptiq
                </span>
            </div>

            {/* Main Nav */}
            <div className="flex-1 w-full flex flex-col gap-2 px-3">
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
                                    ? "bg-canvas text-primary"
                                    : "text-secondary hover:bg-canvas hover:text-primary",
                                !isActive && "group-hover:justify-start justify-center"
                            )}
                        >
                            <div className={clsx("flex items-center justify-center", !isActive && "w-full group-hover:w-auto")}>
                                <Icon className="w-5 h-5 shrink-0" strokeWidth={1.5} />
                            </div>
                            <span className="hidden group-hover:block ml-3 text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-300 delay-100">
                                {item.label}
                            </span>
                        </Link>
                    );
                })}
            </div>

            {/* Bottom Actions */}
            <div className="w-full px-3 pb-2 mt-auto">
                <Link
                    href="/settings"
                    className={clsx(
                        "flex items-center h-10 px-3 rounded-lg transition-colors duration-200 mb-2",
                        pathname.startsWith("/settings")
                            ? "bg-canvas text-primary"
                            : "text-secondary hover:bg-canvas hover:text-primary",
                        "justify-center group-hover:justify-start"
                    )}
                >
                    <div className={clsx("flex items-center justify-center", "w-full group-hover:w-auto")}>
                        <Settings className="w-5 h-5 shrink-0" strokeWidth={1.5} />
                    </div>
                    <span className="hidden group-hover:block ml-3 text-sm font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-300 delay-100">
                        Settings
                    </span>
                </Link>

                {/* User Profile */}
                <div className="mt-4 flex items-center justify-center group-hover:justify-start group-hover:px-3 cursor-pointer hover:bg-canvas rounded-lg p-2 transition-colors relative" onClick={handleLogout} title="Click to log out">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 border border-white/10 shadow-sm flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                        {initials}
                    </div>
                    <div className="hidden group-hover:flex flex-col ml-3 overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-300 delay-100">
                        <span className="text-xs font-medium text-primary truncate">{user?.name || "User"}</span>
                        <div className="flex items-center gap-1">
                            {isSyncing ? (
                                <>
                                    <Loader2 className="w-3 h-3 animate-spin text-accent" />
                                    <span className="text-[10px] text-secondary truncate">Syncing...</span>
                                </>
                            ) : (
                                <span className="text-[10px] text-secondary truncate">Online</span>
                            )}
                        </div>
                    </div>
                    {/* Logout Hint on Hover (only when expanded) */}
                    <div className="hidden group-hover:flex absolute right-2 text-secondary opacity-0 hover:opacity-100 transition-opacity">
                        <LogOut className="w-4 h-4" />
                    </div>
                </div>
            </div>
        </nav>
    );
}
