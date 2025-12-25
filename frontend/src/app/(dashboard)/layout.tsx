import { NavRail } from "@/components/layout/NavRail";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen overflow-hidden bg-canvas">
            <NavRail />
            <div className="flex flex-col flex-1 overflow-hidden">
                <TopBar />
                <main className="flex-1 overflow-y-auto no-scrollbar">
                    <div className="max-w-[1440px] mx-auto p-12">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
