"use client";

import { cn } from "@/lib/utils";

interface AcousticLabel {
  head: string;
  label: string;
  score: number;
  start_ms: number;
  end_ms: number;
}

interface AcousticStripProps {
  labels: AcousticLabel[];
  className?: string;
}

const headColors: Record<string, string> = {
  emotion: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300",
  prosody: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  stress: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  fluency: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
};

export function AcousticStrip({ labels, className }: AcousticStripProps) {
  if (labels.length === 0) return null;

  return (
    <div className={cn("space-y-1", className)}>
      <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
        Acoustic Labels
      </h4>
      <div className="flex flex-wrap gap-1.5">
        {labels.map((l, i) => (
          <span
            key={`${l.head}-${l.start_ms}-${i}`}
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
              headColors[l.head] ?? "bg-zinc-100 text-zinc-700"
            }`}
            title={`${l.head}: ${l.label} (${(l.score * 100).toFixed(0)}%)`}
          >
            {l.head}
            <span className="opacity-70">{l.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
