export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-[calc(100vh-var(--topbar-height)-76px)] md:h-[calc(100vh-var(--topbar-height))] overflow-hidden -mx-4 md:-mx-7 xl:-mx-9 -mb-24 md:-mb-8">
      {children}
    </div>
  );
}
