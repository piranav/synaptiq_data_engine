import { NavRail } from "@/components/layout/NavRail";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="min-h-screen bg-canvas">
            <NavRail />
            <div className="flex flex-col min-h-screen">
                <TopBar />
                <main className="flex-1 pl-[64px]">
                    <div className="max-w-[1440px] mx-auto p-12">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
