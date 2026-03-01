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
  LogOut,
  MoreHorizontal,
  ArrowUpRight,
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "@/contexts/AuthContext";
import { dashboardService } from "@/lib/api/dashboard";
import { useState, useEffect } from "react";
import { authService } from "@/lib/api/auth";

const navItems = [
  { label: "Home", short: "Home", icon: LayoutGrid, href: "/home" },
  { label: "Connections", short: "Connections", icon: Network, href: "/graph" },
  { label: "Notes", short: "Notes", icon: PenLine, href: "/notes" },
  { label: "Sources", short: "Sources", icon: Library, href: "/library" },
  { label: "Chat", short: "Chat", icon: MessageSquare, href: "/chat" },
] as const;

function isRouteActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavRail() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const [isSyncing, setIsSyncing] = useState(false);
  const [showMobileMore, setShowMobileMore] = useState(false);

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
    ? user.name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .slice(0, 2)
      .toUpperCase()
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
    <>
      <nav className="glass-sidebar hidden md:flex h-full shrink-0 border-r border-border flex-col py-3 px-2.5 md:w-[88px] xl:w-[220px]">
        <div className="mb-5 flex items-center px-1">
          <div className="h-10 w-10 rounded-[6px] border border-border bg-surface/85 text-primary inline-flex items-center justify-center">
            <ArrowUpRight className="h-4 w-4" strokeWidth={2} />
          </div>
        </div>

        <div className="hidden xl:block px-1 mb-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-primary">[SYNAPTIQ]</p>
        </div>

        <div className="flex-1 space-y-1">
          {navItems.map((item) => {
            const active = isRouteActive(pathname, item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.short}
                aria-label={item.short}
                className={clsx(
                  "group relative flex h-10 items-center rounded-[6px] border transition-colors",
                  "md:justify-center xl:justify-start xl:px-3 xl:gap-2.5",
                  active
                    ? "border-[color:var(--border-strong)] bg-[var(--surface-strong)] text-primary"
                    : "border-transparent text-tertiary hover:text-secondary hover:border-border-subtle hover:bg-surface/55"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" strokeWidth={1.9} />
                <span className="hidden xl:inline text-[11px] uppercase tracking-[0.15em]">
                  {item.label}
                </span>
                {active && <span className="absolute right-2 hidden xl:block h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />}
              </Link>
            );
          })}
        </div>

        <div className="mt-4 border-t border-border-subtle pt-3 space-y-1">
          <Link
            href="/settings"
            title="Settings"
            aria-label="Settings"
            className={clsx(
              "group relative flex h-10 items-center rounded-[6px] border transition-colors",
              "md:justify-center xl:justify-start xl:px-3 xl:gap-2.5",
              isRouteActive(pathname, "/settings")
                ? "border-[color:var(--border-strong)] bg-[var(--surface-strong)] text-primary"
                : "border-transparent text-tertiary hover:text-secondary hover:border-border-subtle hover:bg-surface/55"
            )}
          >
            <Settings className="h-4 w-4" strokeWidth={1.8} />
            <span className="hidden xl:inline text-[11px] uppercase tracking-[0.15em]">System</span>
          </Link>

          <button
            type="button"
            onClick={handleLogout}
            title="Log out"
            aria-label="Log out"
            className="relative flex h-10 w-full items-center rounded-[6px] border border-transparent transition-colors md:justify-center xl:justify-start xl:px-3 xl:gap-2.5 text-tertiary hover:text-secondary hover:border-border-subtle hover:bg-surface/55"
          >
            {user?.avatar_url ? (
              <Image
                src={user.avatar_url}
                alt={`${user?.name || "User"} avatar`}
                className="h-7 w-7 rounded-[5px] border border-border object-cover"
                width={28}
                height={28}
                unoptimized
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="h-7 w-7 rounded-[5px] border border-border bg-elevated inline-flex items-center justify-center text-[10px] font-medium text-primary">
                {initials}
              </div>
            )}
            <span className="hidden xl:inline text-[11px] uppercase tracking-[0.15em] truncate max-w-[122px]">
              {user?.name || "Log out"}
            </span>
            <LogOut className="hidden xl:block h-3.5 w-3.5 ml-auto" strokeWidth={1.9} />
            <span
              className={clsx(
                "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border border-[var(--canvas-elevated)]",
                isSyncing ? "bg-warning animate-pulse" : "bg-success"
              )}
            />
          </button>

          <p className="hidden xl:block px-1 pt-1 text-[10px] uppercase tracking-[0.12em] text-tertiary">
            {isSyncing ? "Sync in progress" : "System online"}
          </p>
        </div>
      </nav>

      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-border glass px-1.5 pt-1.5 pb-[calc(env(safe-area-inset-bottom)+8px)]">
        <div className="flex items-end justify-between gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isRouteActive(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setShowMobileMore(false)}
                className={clsx(
                  "flex-1 min-w-0 rounded-[6px] border px-1 py-1.5 text-center transition-colors",
                  active
                    ? "border-[color:var(--border-strong)] bg-[var(--surface-strong)] text-primary"
                    : "border-border-subtle bg-surface/70 text-secondary"
                )}
              >
                <Icon className="mx-auto h-4 w-4" strokeWidth={1.9} />
                <p className="mt-1 truncate text-[10px] uppercase tracking-[0.12em]">{item.short}</p>
              </Link>
            );
          })}

          <button
            type="button"
            onClick={() => setShowMobileMore(true)}
            className="w-[54px] shrink-0 rounded-[6px] border border-border-subtle bg-surface/70 px-1 py-1.5 text-secondary"
            aria-label="More actions"
          >
            <MoreHorizontal className="mx-auto h-4 w-4" />
            <p className="mt-1 text-[10px] uppercase tracking-[0.12em]">More</p>
          </button>
        </div>
      </div>

      {showMobileMore && (
        <div className="md:hidden fixed inset-0 z-50">
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setShowMobileMore(false)}
            className="absolute inset-0 bg-black/48"
          />
          <div className="absolute inset-x-3 bottom-24 rounded-[10px] overlay-menu p-3 animation-scale-in">
            <Link
              href="/settings"
              onClick={() => setShowMobileMore(false)}
              className="h-11 px-3 rounded-[6px] border border-border bg-surface text-primary flex items-center"
            >
              <Settings className="h-4 w-4 mr-2" /> Settings
            </Link>
            <div className="mt-2 h-11 px-3 rounded-[6px] border border-border bg-surface text-secondary flex items-center justify-between">
              <span className="text-sm">Sync status</span>
              <span className={clsx("inline-flex items-center gap-1 text-xs", isSyncing ? "text-warning" : "text-success")}>
                <span className={clsx("h-2 w-2 rounded-full", isSyncing ? "bg-warning animate-pulse" : "bg-success")} />
                {isSyncing ? "Syncing" : "Online"}
              </span>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="mt-2 h-11 w-full rounded-[6px] border border-danger/40 bg-danger/10 text-danger flex items-center px-3"
            >
              <LogOut className="h-4 w-4 mr-2" /> Log out
            </button>
          </div>
        </div>
      )}
    </>
  );
}
