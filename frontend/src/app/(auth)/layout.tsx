import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full bg-[var(--canvas)] app-grid-bg">
      <div className="hidden lg:flex w-1/2 relative flex-col items-center justify-center p-12 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(111,224,255,0.12),transparent_35%),radial-gradient(circle_at_80%_78%,rgba(255,191,95,0.12),transparent_40%)]" />

        <div className="relative z-10 w-[460px] h-[460px] rounded-full border border-border bg-surface">
          <div className="absolute inset-[15%] rounded-full border border-border-subtle" />
          <div className="absolute inset-[30%] rounded-full border border-border-subtle" />
          <div className="absolute inset-[45%] rounded-full border border-border-subtle" />

          <span className="absolute top-[22%] left-[26%] h-2.5 w-2.5 rounded-full bg-node-source shadow-[0_0_18px_rgba(109,255,154,0.45)]" />
          <span className="absolute top-[36%] right-[24%] h-2 w-2 rounded-full bg-node-concept shadow-[0_0_18px_rgba(111,224,255,0.42)]" />
          <span className="absolute bottom-[25%] left-[36%] h-2.5 w-2.5 rounded-full bg-node-definition shadow-[0_0_18px_rgba(255,191,95,0.45)]" />
          <span className="absolute inset-[48%] h-4 w-4 rounded-full bg-[var(--accent)] shadow-[0_0_28px_rgba(109,255,154,0.42)]" />
        </div>

        <div className="relative z-10 max-w-sm text-center mt-12">
          <blockquote className="text-title-3 text-primary font-medium leading-relaxed">
            &quot;The most powerful tool for thought is the one that connects your ideas.&quot;
          </blockquote>
          <div className="mt-6 w-8 h-px bg-border mx-auto" />
          <p className="mt-4 text-callout text-secondary">Synaptiq</p>
        </div>
      </div>

      <div className="flex w-full lg:w-1/2 flex-col bg-surface/45 relative">
        <div className="absolute top-8 left-8">
          <Link href="/" className="inline-flex items-center text-secondary hover:text-primary transition-colors gap-2 text-body-small">
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </div>

        <div className="flex-1 flex flex-col justify-center px-6 sm:px-10 md:px-16 lg:px-[72px] pt-24 pb-8 max-w-[640px] mx-auto w-full">
          <div className="dashboard-card p-6 sm:p-8">{children}</div>
        </div>

        <div className="py-6 text-center text-callout text-tertiary">&copy; {new Date().getFullYear()} Synaptiq. All rights reserved.</div>
      </div>
    </div>
  );
}
