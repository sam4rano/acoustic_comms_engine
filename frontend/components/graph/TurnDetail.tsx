import type { TurnNode } from "@/types";
import { AcousticStrip } from "@/components/session/AcousticStrip";

interface TurnDetailProps {
  turn: TurnNode;
}

export function TurnDetail({ turn }: TurnDetailProps) {
  const acousticLabels = Object.entries(turn.acoustic_labels).map(([head, label]) => ({
    head,
    label,
    score: 1,
    start_ms: 0,
    end_ms: 0,
  }));

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-500">{turn.speaker_label}</span>
        <span className="text-[10px] text-zinc-400">
          {turn.start_ms}ms – {turn.end_ms}ms
        </span>
      </div>
      <p className="mt-2 text-sm text-zinc-900 dark:text-zinc-100">{turn.text}</p>
      <div className="mt-2 flex items-center gap-2 text-[10px] text-zinc-400">
        <span>Confidence: {Math.round(turn.confidence * 100)}%</span>
      </div>
      {acousticLabels.length > 0 && <AcousticStrip labels={acousticLabels} className="mt-3" />}
    </div>
  );
}
