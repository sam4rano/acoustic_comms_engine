import type { CoachingAction } from "@/types";
import { cn } from "@/lib/utils";

interface CoachingCardsProps {
  actions: CoachingAction[];
}

const priorityStyles: Record<string, string> = {
  high: "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20",
  medium: "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20",
  low: "border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800/50",
};

const priorityDot: Record<string, string> = {
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-zinc-400",
};

export function CoachingCards({ actions }: CoachingCardsProps) {
  if (actions.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No coaching actions generated.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {actions.map((action, i) => (
        <div
          key={`${action.dimension}-${i}`}
          className={cn(
            "rounded-xl border p-4",
            priorityStyles[action.priority],
          )}
        >
          <div className="flex items-start gap-3">
            <span
              className={cn(
                "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                priorityDot[action.priority],
              )}
            />
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                  {action.dimension}
                </span>
                <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-[10px] font-medium capitalize text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300">
                  {action.priority}
                </span>
              </div>
              <h4 className="font-semibold text-zinc-900 dark:text-zinc-100">
                {action.title}
              </h4>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {action.description}
              </p>
              <p className="text-xs text-teal-600 dark:text-teal-400">
                Tip: {action.practice_tip}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
