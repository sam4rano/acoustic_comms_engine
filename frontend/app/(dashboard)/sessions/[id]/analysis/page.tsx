import type { Metadata } from "next";
import { BarChart3 } from "lucide-react";

export const metadata: Metadata = {
  title: "Analysis — Acoustic Comms",
};

export default async function AnalysisPage({
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
            Analysis
          </h1>
          <p className="text-sm text-zinc-500 font-mono">{id}</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-5 w-5 text-teal-600 dark:text-teal-400" />
            <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
              Communication Scores
            </h2>
          </div>
          <p className="mt-3 text-sm text-zinc-500">
            Dimension scores will render here after analysis completes.
          </p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
            Coaching Actions
          </h2>
          <p className="mt-3 text-sm text-zinc-500">
            Personalized coaching recommendations will appear here.
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
          Agent Trace
        </h2>
        <p className="mt-3 text-sm text-zinc-500">
          Reasoning pipeline trace will be displayed here.
        </p>
      </div>
    </div>
  );
}
