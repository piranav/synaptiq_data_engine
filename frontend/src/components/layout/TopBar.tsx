"use client";

import Image from "next/image";
import clsx from "clsx";
import { Monitor, Moon, Sun } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";

const themeItems = [
  { mode: "light", label: "Light", icon: Sun },
  { mode: "dark", label: "Dark", icon: Moon },
  { mode: "system", label: "System", icon: Monitor },
] as const;

function getSectionTag(pathname: string) {
  if (pathname.startsWith("/home")) return "[SURFACE]";
  if (pathname.startsWith("/graph")) return "[TOPOLOGY]";
  if (pathname.startsWith("/notes")) return "[NOTES]";
  if (pathname.startsWith("/library")) return "[ARCHIVE]";
  if (pathname.startsWith("/chat")) return "[CHANNEL]";
  if (pathname.startsWith("/settings")) return "[SYSTEM]";
  return "[SYNAPTIQ]";
}

export function TopBar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { themeMode, setThemeMode } = useTheme();

  const initials = user?.name
    ? user.name
      .split(" ")
      .map((name) => name[0])
      .join("")
      .slice(0, 2)
      .toUpperCase()
    : "?";

  return (
    <header className="sticky top-0 z-30 glass border-b border-border px-3 md:px-5 xl:px-7 h-[var(--topbar-height)] flex items-center justify-between gap-3">
      <div className="min-w-0 flex items-center gap-3">
        <p className="text-[11px] uppercase tracking-[0.2em] text-tertiary font-medium">
          {getSectionTag(pathname)}
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div className="hidden md:flex items-center gap-1 rounded-[6px] border border-border bg-surface/70 p-1">
          {themeItems.map((item) => {
            const Icon = item.icon;
            const isActive = themeMode === item.mode;

            return (
              <button
                key={item.mode}
                onClick={() => setThemeMode(item.mode)}
                title={item.label}
                aria-label={item.label}
                className={clsx(
                  "h-7 w-7 rounded-[4px] inline-flex items-center justify-center border transition-colors",
                  isActive
                    ? "bg-[var(--active-bg)] text-primary border-[color:var(--border-strong)]"
                    : "text-secondary border-transparent hover:bg-[var(--hover-bg)] hover:text-primary"
                )}
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => setThemeMode(themeMode === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
          className="md:hidden h-9 w-9 rounded-[6px] border border-border bg-surface/70 text-secondary hover:text-primary hover:bg-[var(--hover-bg)] transition-colors inline-flex items-center justify-center"
        >
          {themeMode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <div className="h-9 w-9 overflow-hidden rounded-[6px] border border-border bg-elevated inline-flex items-center justify-center text-[11px] font-medium text-primary">
          {user?.avatar_url ? (
            <Image
              src={user.avatar_url}
              alt={`${user?.name || "User"} avatar`}
              className="h-full w-full object-cover"
              width={36}
              height={36}
              unoptimized
              referrerPolicy="no-referrer"
            />
          ) : (
            initials
          )}
        </div>
      </div>
    </header>
  );
}
