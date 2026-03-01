import Link from "next/link";
import { ArrowRight, LogIn } from "lucide-react";

export default function Home() {
  return (
    <main className="relative min-h-screen app-grid-bg bg-[var(--canvas)] px-6 py-12 md:px-10 md:py-16 flex items-center justify-center">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_18%_20%,rgba(111,224,255,0.12),transparent_35%),radial-gradient(circle_at_84%_78%,rgba(255,191,95,0.12),transparent_42%)]" />

      <section className="relative w-full max-w-[980px] dashboard-card rounded-[16px] p-8 md:p-12 text-center">
        <p className="inline-flex items-center gap-2 dashboard-pill px-3 py-1 text-[11px] uppercase tracking-[0.15em] text-secondary">
          Synaptiq Workspace
        </p>

        <h1 className="mt-6 text-display text-primary leading-[1.05]">
          Build Your Knowledge Surface
        </h1>
        <p className="mt-4 mx-auto max-w-[640px] text-body text-secondary">
          A cinematic, connected environment for notes, sources, graph insights, and conversations.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/login"
            className="h-11 px-5 rounded-xl border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] font-medium inline-flex items-center gap-2 hover:bg-[var(--hover-bg)] transition-colors"
          >
            <LogIn className="w-4 h-4" />
            Sign In
          </Link>
          <Link
            href="/signup"
            className="h-11 px-5 rounded-xl border border-border bg-surface text-primary font-medium inline-flex items-center gap-2 hover:bg-[var(--hover-bg)] transition-colors"
          >
            Create Account
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </main>
  );
}
