"use client";

import { useRef, useEffect } from "react";

interface TranscriptEntry {
  turn_id: string;
  speaker_label: string;
  text: string;
  is_final: boolean;
  timestamp: number;
}

interface TranscriptPanelProps {
  entries: TranscriptEntry[];
}

export function TranscriptPanel({ entries }: TranscriptPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Transcript</h3>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {entries.map((entry) => (
          <div
            key={entry.turn_id}
            className={`rounded-lg p-3 ${
              entry.is_final
                ? "bg-zinc-50 dark:bg-zinc-800/50"
                : "bg-teal-50 dark:bg-teal-900/20"
            }`}
          >
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
              {entry.speaker_label}
            </span>
            <p
              className={`mt-1 text-sm ${
                entry.is_final
                  ? "text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 italic dark:text-zinc-400"
              }`}
            >
              {entry.text}
            </p>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
