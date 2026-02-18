export default function ChatLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="h-[calc(100vh-var(--topbar-height))] overflow-hidden -mx-5 md:-mx-8 -mb-8">
            {children}
        </div>
    );
}
