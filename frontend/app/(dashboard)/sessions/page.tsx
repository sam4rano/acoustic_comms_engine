import type { Metadata } from "next";
import Link from "next/link";
import { Mic, PlusCircle } from "lucide-react";
import { EmptyState } from "@/components/layout/EmptyState";

export const metadata: Metadata = {
  title: "Sessions — Acoustic Comms",
};

export default function SessionsPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Sessions</h1>
        <Link
          href="/dashboard/sessions/new"
          className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <PlusCircle className="h-4 w-4" />
          New Session
        </Link>
      </div>

      <EmptyState
        icon={<Mic className="h-12 w-12" />}
        title="No sessions recorded"
        description="Your recorded sessions will appear here. Start a new session to begin."
        action={
          <Link
            href="/dashboard/sessions/new"
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            Start a Session
          </Link>
        }
      />
    </div>
  );
}
