import { cn } from "@/lib/utils";
import type { DimensionScore } from "@/types";

interface ScoreCardProps {
  dimension: DimensionScore;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-teal-600 dark:text-teal-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 80) return "bg-teal-50 dark:bg-teal-900/20";
  if (score >= 60) return "bg-amber-50 dark:bg-amber-900/20";
  return "bg-red-50 dark:bg-red-900/20";
}

export function ScoreCard({ dimension }: ScoreCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-200 p-4 dark:border-zinc-800",
        scoreBg(dimension.score),
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium capitalize text-zinc-700 dark:text-zinc-300">
          {dimension.dimension}
        </span>
        <span className={cn("text-2xl font-bold", scoreColor(dimension.score))}>
          {dimension.score}
          <span className="text-xs font-normal text-zinc-400">/100</span>
        </span>
      </div>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
        {dimension.rationale}
      </p>
      <div className="mt-2 flex items-center gap-1">
        <div className="h-1.5 flex-1 rounded-full bg-zinc-200 dark:bg-zinc-700">
          <div
            className={cn(
              "h-1.5 rounded-full transition-all",
              dimension.confidence >= 0.7
                ? "bg-teal-500"
                : dimension.confidence >= 0.4
                  ? "bg-amber-500"
                  : "bg-red-500",
            )}
            style={{ width: `${dimension.confidence * 100}%` }}
          />
        </div>
        <span className="text-[10px] text-zinc-400">
          {Math.round(dimension.confidence * 100)}% confidence
        </span>
      </div>
    </div>
  );
}
