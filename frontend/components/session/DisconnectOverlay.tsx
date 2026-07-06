"use client";

import { WifiOff } from "lucide-react";

interface DisconnectOverlayProps {
  visible: boolean;
  onRetry: () => void;
}

export function DisconnectOverlay({ visible, onRetry }: DisconnectOverlayProps) {
  if (!visible) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center rounded-xl bg-black/40 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-3 rounded-xl bg-white p-8 shadow-lg dark:bg-zinc-900">
        <WifiOff className="h-10 w-10 text-amber-500" />
        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          Connection Lost
        </p>
        <p className="text-xs text-zinc-500">Attempting to reconnect...</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          Retry Now
        </button>
      </div>
    </div>
  );
}
