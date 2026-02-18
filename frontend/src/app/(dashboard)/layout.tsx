import { NavRail } from "@/components/layout/NavRail";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="dashboard-swiss min-h-screen bg-[var(--canvas)] p-3 md:p-5">
            <div className="dashboard-board flex h-[calc(100vh-1.5rem)] md:h-[calc(100vh-2.5rem)] overflow-hidden">
                <NavRail />
                <div className="flex flex-col flex-1 overflow-hidden">
                    <TopBar />
                    <main className="flex-1 overflow-y-auto no-scrollbar">
                        <div className="max-w-[1480px] mx-auto px-5 md:px-8 pb-8">
                            {children}
                        </div>
                    </main>
                </div>
            </div>
        </div>
    );
}
