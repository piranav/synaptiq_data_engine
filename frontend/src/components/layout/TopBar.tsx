"use client";

import { useEffect, useState, useRef } from "react";
import { Search, Bell, User, Loader2, Settings, LogOut, CheckCircle2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { dashboardService } from "@/lib/api/dashboard";
import { authService } from "@/lib/api/auth";
import Link from "next/link";
import clsx from "clsx";

export function TopBar() {
    const pathname = usePathname();
    const router = useRouter();
    const { user } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    const title = pathname.split("/")[1] || "Home";
    const displayTitle = title.charAt(0).toUpperCase() + title.slice(1);

    const initials = user?.name
        ? user.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()
        : "PK";

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
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

    const handleLogout = async () => {
        try {
            await authService.logout();
            router.push("/login");
        } catch (error) {
            console.error("Logout failed", error);
        }
    };

    return (
        <header className="h-[56px] pl-[64px] pr-8 flex items-center justify-between border-b border-border bg-surface/80 backdrop-blur-md sticky top-0 z-40">
            <div className="pl-6">
                {displayTitle !== "Home" && (
                    <h1 className="text-title-3 text-primary">{displayTitle}</h1>
                )}
            </div>

            <div className="flex items-center gap-4">
                {/* Sync Status */}
                <div className="hidden sm:flex items-center gap-2 mr-2">
                    {isSyncing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin text-accent" />
                            <span className="text-caption text-secondary">Syncing...</span>
                        </>
                    ) : (
                        <div className="group flex items-center gap-2 opacity-50 hover:opacity-100 transition-opacity">
                            <CheckCircle2 className="w-4 h-4 text-success" />
                            <span className="text-caption text-secondary hidden group-hover:inline">Synced</span>
                        </div>
                    )}
                </div>

                {/* Command Palette Trigger */}
                <button className="hidden sm:flex items-center h-9 px-3 bg-canvas rounded-lg border border-border text-tertiary w-64 hover:border-accent hover:text-secondary transition-colors group">
                    <Search className="w-4 h-4 mr-2" />
                    <span className="text-callout">Search...</span>
                    <span className="ml-auto text-xs px-1.5 py-0.5 rounded border border-border-subtle bg-surface text-tertiary group-hover:border-accent/20">⌘K</span>
                </button>

                <button className="w-9 h-9 flex items-center justify-center rounded-full text-secondary hover:bg-border-subtle hover:text-primary transition-colors">
                    <Bell className="w-5 h-5" />
                </button>

                {/* Avatar Menu */}
                <div className="relative" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-transparent hover:ring-offset-2 hover:ring-accent transition-all"
                    >
                        {initials}
                    </button>

                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-2 w-80 bg-[#1C1C1E] dark:bg-[#2C2C2E] rounded-3xl shadow-2xl py-4 z-[100] animation-fade-in origin-top-right overflow-hidden ring-1 ring-white/10 flex flex-col items-center text-center">
                            <div className="px-6 pb-4 border-b border-white/10 w-full mb-2">
                                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xl font-semibold mb-3 mx-auto">
                                    {initials}
                                </div>
                                <p className="text-title-3 font-medium text-primary truncate leading-tight">Hi, {user?.name?.split(" ")[0] || "User"}!</p>
                                <p className="text-body-small text-secondary truncate mt-1">{user?.email}</p>
                                <button className="mt-3 px-4 py-1.5 rounded-full border border-white/20 text-body-small text-primary hover:bg-white/10 transition-colors">
                                    Manage your account
                                </button>
                            </div>

                            <div className="px-2 w-full space-y-1">
                                <Link
                                    href="/settings"
                                    className="flex items-center gap-3 px-4 py-3 rounded-xl text-body-small text-primary hover:bg-white/5 transition-colors text-left w-full"
                                    onClick={() => setIsMenuOpen(false)}
                                >
                                    <Settings className="w-5 h-5 text-secondary" />
                                    Settings
                                </Link>

                                <button
                                    onClick={handleLogout}
                                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-body-small text-primary hover:bg-white/5 transition-colors text-left"
                                >
                                    <LogOut className="w-5 h-5 text-secondary" />
                                    Log out
                                </button>
                            </div>

                            <div className="mt-2 pt-2 border-t border-white/10 w-full flex justify-center gap-4 text-xs text-tertiary">
                                <span className="hover:text-secondary cursor-pointer">Privacy Policy</span>
                                <span>•</span>
                                <span className="hover:text-secondary cursor-pointer">Terms of Service</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}
