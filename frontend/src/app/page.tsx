import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-display mb-4">Synaptiq</h1>
      <p className="text-body text-secondary mb-8">Personal Knowledge System</p>

      <div className="flex gap-4">
        <Link href="/login" className="text-accent hover:underline">
          Sign In
        </Link>
        <Link href="/signup" className="text-accent hover:underline">
          Sign Up
        </Link>
      </div>
    </main>
  );
}
