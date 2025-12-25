export default function ChatLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="h-[calc(100vh-56px)] overflow-hidden -m-12">
            {children}
        </div>
    );
}
