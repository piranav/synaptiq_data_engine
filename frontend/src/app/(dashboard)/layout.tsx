"use client";

import clsx from "clsx";
import { usePathname } from "next/navigation";
import { NavRail } from "@/components/layout/NavRail";
import { TopBar } from "@/components/layout/TopBar";
import { GridFrame } from "@/components/layout/GridFrame";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isChatRoute = pathname === "/chat" || pathname.startsWith("/chat/");

  return (
    <div className="dashboard-swiss app-grid-bg min-h-screen bg-[var(--canvas)] p-2 md:p-4">
      <div className="dashboard-board flex min-h-[calc(100vh-1rem)] md:min-h-[calc(100vh-2rem)] overflow-hidden">
        <GridFrame className="hidden md:block" />
        <div className="relative z-[2] flex min-h-full w-full overflow-hidden">
          <NavRail />
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <TopBar />
            <main className="flex-1 overflow-y-auto no-scrollbar">
              <div
                className={clsx(
                  "w-full px-4 md:px-7 xl:px-9 pb-24 md:pb-8",
                  isChatRoute ? "max-w-none" : "mx-auto max-w-[1520px]",
                )}
              >
                {children}
              </div>
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}
