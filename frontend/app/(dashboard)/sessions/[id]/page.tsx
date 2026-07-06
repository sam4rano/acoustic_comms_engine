import type { Metadata } from "next";
import Link from "next/link";
import { BarChart3, Share2 } from "lucide-react";

export const metadata: Metadata = {
  title: "Session — Acoustic Comms",
};

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Session
          </h1>
          <p className="text-sm text-zinc-500 font-mono">{id}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/dashboard/sessions/${id}/analysis`}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            <BarChart3 className="h-4 w-4" />
            Analysis
          </Link>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
          >
            <Share2 className="h-4 w-4" />
            Share
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm text-zinc-500">
          Live session or replay view for <span className="font-mono text-zinc-700 dark:text-zinc-300">{id}</span>.
        </p>
      </div>
    </div>
  );
}
