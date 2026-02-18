"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
    LayoutGrid,
    Network,
    PenLine,
    Library,
    MessageSquare,
    Settings,
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
    const [isMounted, setIsMounted] = useState(false);

    // Ensure we're on the client before rendering avatar to prevent hydration mismatch
    useEffect(() => {
        setIsMounted(true);
    }, []);

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

    // Derive initials only after mount to avoid server/client mismatch (user comes from localStorage on client)
    const initials = !isMounted
        ? "…"
        : user?.name
            ? user.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()
            : "?";

    const handleLogout = async () => {
        try {
            await authService.logout();
            router.push("/login");
        } catch (error) {
            console.error("Logout failed", error);
        }
    };

    return (
        <nav className="w-[88px] border-r border-border bg-[var(--glass-sidebar)] backdrop-blur-sm flex h-full flex-col items-center py-5 px-3 shrink-0">
            <div className="mb-8 w-full flex justify-center">
                <div className="w-10 h-10 bg-primary text-surface rounded-full flex items-center justify-center text-sm font-semibold tracking-tight">
                    S
                </div>
            </div>

            <div className="flex-1 w-full flex flex-col items-center gap-2">
                {navItems.map((item) => {
                    const isActive = pathname.startsWith(item.href);
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={item.label}
                            aria-label={item.label}
                            className={clsx(
                                "relative w-11 h-11 rounded-full border inline-flex items-center justify-center transition-all duration-200",
                                isActive
                                    ? "bg-[var(--active-bg)] text-accent border-accent/35 shadow-card"
                                    : "bg-surface text-secondary border-border hover:text-primary hover:bg-[var(--hover-bg)]"
                            )}
                        >
                            <Icon className="w-[18px] h-[18px]" strokeWidth={1.9} />
                            {isActive && (
                                <span className="absolute -right-1.5 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-accent" />
                            )}
                        </Link>
                    );
                })}
            </div>

            <div className="w-full mt-auto flex flex-col items-center gap-2">
                <Link
                    href="/settings"
                    title="Settings"
                    aria-label="Settings"
                    className={clsx(
                        "relative w-11 h-11 rounded-full border inline-flex items-center justify-center transition-all duration-200",
                        pathname.startsWith("/settings")
                            ? "bg-[var(--active-bg)] text-accent border-accent/35 shadow-card"
                            : "bg-surface text-secondary border-border hover:text-primary hover:bg-[var(--hover-bg)]"
                    )}
                >
                    <Settings className="w-[18px] h-[18px]" strokeWidth={1.85} />
                </Link>

                <button
                    type="button"
                    onClick={handleLogout}
                    title="Log out"
                    aria-label="Log out"
                    className="mt-2 w-11 h-11 rounded-full border border-border bg-surface hover:bg-[var(--hover-bg)] transition-colors relative inline-flex items-center justify-center"
                >
                    {isMounted && user?.avatar_url ? (
                        <Image
                            src={user.avatar_url}
                            alt={`${user?.name || "User"} avatar`}
                            className="w-8 h-8 rounded-full border border-border object-cover"
                            width={32}
                            height={32}
                            unoptimized
                            referrerPolicy="no-referrer"
                        />
                    ) : (
                        <div className="w-8 h-8 rounded-full bg-[var(--elevated)] border border-border flex items-center justify-center text-primary text-[11px] font-semibold">
                            {initials}
                        </div>
                    )}
                    {isSyncing ? (
                        <span className="absolute -right-0.5 -top-0.5 h-4 w-4 rounded-full border border-border bg-surface text-accent inline-flex items-center justify-center">
                            <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        </span>
                    ) : (
                        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-success border border-surface" />
                    )}
                </button>
                <span className="sr-only">{isSyncing ? "Syncing" : "Online"}</span>
            </div>
        </nav>
    );
}
