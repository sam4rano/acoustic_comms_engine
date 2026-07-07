"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Mic, PlusCircle, Clock, BarChart3 } from "lucide-react";
import { EmptyState } from "@/components/layout/EmptyState";
import { hasCachedAnalysis } from "@/lib/analysis-cache";

interface Session {
  id: string;
  title: string;
  language: string;
  status: string;
  created_at: string;
  turn_count: number;
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    fetch(`${apiUrl}/sessions`)
      .then((r) => r.json())
      .then((data) => setSessions(data.sessions ?? []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Sessions</h1>
        <Link
          href="/sessions/new"
          className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <PlusCircle className="h-4 w-4" />
          New Session
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-500">Loading...</p>
      ) : sessions.length === 0 ? (
        <EmptyState
          icon={<Mic className="h-12 w-12" />}
          title="No sessions recorded"
          description="Your recorded sessions will appear here. Start a new session to begin."
          action={
            <Link
              href="/sessions/new"
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
            >
              Start a Session
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => {
            const hasAnalysis = hasCachedAnalysis(s.id);
            return (
            <Link
              key={s.id}
              href={hasAnalysis ? `/sessions/${s.id}/analysis` : `/sessions/${s.id}`}
              className="block rounded-xl border border-zinc-200 bg-white p-4 transition hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-zinc-900 dark:text-zinc-100">{s.title}</h3>
                    {hasAnalysis && (
                      <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                        Analyzed
                      </span>
                    )}
                  </div>
                  <p className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                    <Clock className="h-3 w-3" />
                    {new Date(s.created_at).toLocaleString()}
                    <span className="capitalize">{s.status}</span>
                  </p>
                </div>
                <BarChart3 className="h-5 w-5 text-zinc-400" />
              </div>
            </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
