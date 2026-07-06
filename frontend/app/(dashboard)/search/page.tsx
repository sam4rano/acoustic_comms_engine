import type { Metadata } from "next";
import { Search } from "lucide-react";

export const metadata: Metadata = {
  title: "Search — Acoustic Comms",
};

export default function SearchPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Search</h1>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
        <input
          type="search"
          placeholder="Search transcripts, sessions, analysis..."
          className="block w-full rounded-xl border border-zinc-300 bg-white py-3 pl-10 pr-4 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
      </div>

      <p className="text-center text-sm text-zinc-500">
        Search across all your sessions and analysis results.
      </p>
    </div>
  );
}
