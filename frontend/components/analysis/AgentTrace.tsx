"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle, AlertCircle, Clock } from "lucide-react";
import type { AgentStepTrace } from "@/types";
import { cn } from "@/lib/utils";

interface AgentTraceProps {
  trace: AgentStepTrace[];
}

function AgentIcon({ agent, error }: { agent: string; error?: string | null }) {
  if (error) return <AlertCircle className="h-4 w-4 text-red-500" />;
  if (agent === "Verifier" || agent === "Scorer") return <CheckCircle className="h-4 w-4 text-teal-500" />;
  return <Clock className="h-4 w-4 text-zinc-400" />;
}

export function AgentTrace({ trace }: AgentTraceProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));

  const toggle = (i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <div className="space-y-1">
      {trace.map((step, i) => {
        const open = expanded.has(i);
        return (
          <div
            key={`${step.agent}-${i}`}
            className={cn(
              "rounded-lg border border-zinc-200 text-sm dark:border-zinc-800",
              step.error ? "border-red-200 dark:border-red-800" : "",
            )}
          >
            <button
              type="button"
              onClick={() => toggle(i)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left"
            >
              {open ? (
                <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />
              )}
              <AgentIcon agent={step.agent} error={step.error} />
              <span className="font-medium text-zinc-800 dark:text-zinc-200">
                {step.agent}
              </span>
              <span className="text-xs text-zinc-400">
                {(step.duration_ms / 1000).toFixed(1)}s
              </span>
              {step.model && (
                <span className="ml-auto text-[10px] text-zinc-400">{step.model}</span>
              )}
            </button>
            {open && (
              <div className="border-t border-zinc-200 px-3 py-2 dark:border-zinc-800">
                <p className="text-xs text-zinc-500">{step.input_summary}</p>
                {step.token_usage && (
                  <p className="mt-1 text-[10px] text-zinc-400">
                    Tokens: {step.token_usage.total_tokens} (
                    {step.token_usage.prompt_tokens} prompt /{" "}
                    {step.token_usage.completion_tokens} completion)
                  </p>
                )}
                {step.error && (
                  <p className="mt-1 text-xs text-red-500">{step.error}</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
