import type { Metadata } from "next";
import Link from "next/link";
import { PlusCircle, Mic, BarChart3 } from "lucide-react";
import { EmptyState } from "@/components/layout/EmptyState";

export const metadata: Metadata = {
  title: "Dashboard — Acoustic Comms",
};

const quickStats = [
  { label: "Total Sessions", value: "—", icon: Mic },
  { label: "Avg Score", value: "—", icon: BarChart3 },
];

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Dashboard</h1>
        <Link
          href="/dashboard/sessions/new"
          className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <PlusCircle className="h-4 w-4" />
          New Session
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {quickStats.map(({ label, value, icon: Icon }) => (
          <div
            key={label}
            className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-teal-50 p-2 dark:bg-teal-900/20">
                <Icon className="h-5 w-5 text-teal-600 dark:text-teal-400" />
              </div>
              <div>
                <p className="text-sm text-zinc-500">{label}</p>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  {value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <EmptyState
        icon={<Mic className="h-12 w-12" />}
        title="No sessions yet"
        description="Start your first communication analysis session to see results here."
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
